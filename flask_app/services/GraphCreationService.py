from datetime import datetime
import sys
import logging
from typing import Dict, List
import json
from flask import current_app
from .SupabaseService import SupabaseService
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.entities.source_node import sourceNode
from flask_app.src.document_sources.youtube import get_documents_from_youtube
from flask_app.src.main import processing_source
from flask_app.src.document_sources.text_loader import get_text_chunks_langchain
from .HelperService import HelperService
from .SimilarityService import SimilarityService
from flask_app.models.Quiz import QuizQuestion


class GraphCreationService:
    @staticmethod
    def create_graph_from_youtube(
        sourceUrl: str,
        noteId: str,
        courseId: str,
        userId: str
    ) -> None:
        try:
            successCount=0
            failedCount=0

            similarityService = SimilarityService(
                similarity_threshold=0.9, 
                word_edit_distance=5
            )

            similar = similarityService.same_youtube_node_exists(course_id=courseId, url=sourceUrl)

            if similar:
                logging.info(f"File: {sourceUrl} is similar to {similar}")
                SupabaseService.update_note(noteId=noteId, key='graphStatus', value='already-exists')
                return

            transcript = HelperService.check_url_source(ytUrl=sourceUrl)

            obj_source_node = sourceNode(
                file_type='text',
                file_source='youtube',
                model=current_app.config['MODEL'],
                courseId=courseId,
                userId=userId,
                url=sourceUrl,
                created_at=datetime.now(),
                noteId=noteId,
                file_size=sys.getsizeof(transcript)
            )
            
            graphDb_data_Access: graphDBdataAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

            fileName, pages = get_documents_from_youtube(obj_source_node.url)

            obj_source_node.noteId = noteId

            graphDb_data_Access.create_source_node(obj_source_node)

            processing_source(
                graphDb_data_Access=graphDb_data_Access,
                fileName=fileName,
                pages=pages,
                allowedNodes=[], 
                allowedRelationship=[],
                userId=userId,
                courseId=courseId,
                noteId=noteId
                )
            
            GraphCreationService.update_communities_for_param(id_type='noteId', target_id=noteId)
            GraphCreationService.update_communities_for_param(id_type='courseId', target_id=courseId)

            SupabaseService.update_note(noteId=noteId, key='sourceUrl', value=sourceUrl)
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='complete')

            logging.info(f'File {fileName} has been processed successfully, success_count: {successCount}, failed_count: {failedCount}')
        except Exception as e:
            logging.exception(f'Exception in create_source_node_graph_url_youtube: {e}')
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')

    @staticmethod
    def create_graph_from_raw_text(  
        noteId: str,
        courseId: str,
        userId: str,
        rawText: str,
        fileName: str
    ) -> None:
            
        try:
            successCount=0
            failedCount=0
            
            pages = get_text_chunks_langchain(rawText)

            similarityService = SimilarityService(
                similarity_threshold=0.9, 
                word_edit_distance=5
            )

            similar = similarityService.has_similar_documents(
                courseId=courseId,
                noteId=noteId,
                documents=pages
            )

            if similar:
                logging.info(f"File: {fileName} is similar to {similar}")
                SupabaseService.update_note(
                    noteId=noteId, 
                    key='graphStatus', 
                    value='already-exists'
                    )
                return

            obj_source_node = sourceNode(
                file_type='text',
                file_source='text',
                model=current_app.config['MODEL'],
                courseId=courseId,
                userId=userId,            
                created_at=datetime.now(),
                noteId=noteId,
                file_size=sys.getsizeof(rawText)
            )

            graphDb_data_Access: graphDBdataAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

            obj_source_node.noteId = noteId

            graphDb_data_Access.create_source_node(obj_source_node)

            processing_source(
                graphDb_data_Access=graphDb_data_Access,
                fileName=fileName,
                pages=pages,
                allowedNodes=[], 
                allowedRelationship=[],
                userId=userId,
                courseId=courseId,
                noteId=noteId
                )
            
            GraphCreationService.update_communities_for_param(id_type='noteId', target_id=noteId)
            GraphCreationService.update_communities_for_param(id_type='courseId', target_id=courseId)
            
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='complete')

            logging.info(f'File {fileName} has been processed successfully, success_count: {successCount}, failed_count: {failedCount}')
        except Exception as e:
            logging.exception(f'Exception: {e}')
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')


    @staticmethod
    def update_communities_for_param(id_type: str, target_id: str) -> Dict:
        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

        try:
            query = f"""
            MATCH (n)-[r]-(relatedNode)
            WHERE "{target_id}" IN n.{id_type} AND "{target_id}" IN relatedNode.{id_type}

            WITH collect(distinct n) + collect(distinct relatedNode) AS nodes, collect(distinct r) AS rels

            CALL gds.graph.project.cypher(
            '{target_id}_temp_graph',
            'UNWIND $nodes AS n RETURN id(n) AS id',
            'UNWIND $rels AS r RETURN id(startNode(r)) AS source, id(endNode(r)) AS target',
            {{parameters: {{nodes: nodes, rels: rels}}}}
            )
            YIELD graphName

            CALL gds.louvain.stream('{target_id}_temp_graph')
            YIELD nodeId, communityId

            WITH gds.util.asNode(nodeId) AS node, communityId

            WITH collect({{node: node, communityId: communityId}}) AS results

            CALL gds.graph.drop('{target_id}_temp_graph') YIELD graphName

            UNWIND results AS result
            RETURN result.node AS node, result.communityId AS communityId
            """

            result = graphAccess.execute_query(query)

            updated_nodes = []

            for record in result:
                node = record['node']
                communityId = record['communityId']

                node[f'{id_type}_{target_id}_community'] = communityId

                updated_nodes.append(node)


            update_query = """
            UNWIND $nodes AS node
            MATCH (n)
            WHERE n.id = node.id
            SET n += node
            RETURN count(n) as updatedCount
            """

            update_result = graphAccess.execute_query(update_query, {'nodes': updated_nodes})

            logging.info(f"Updated nodes: {update_result}")

        except ValueError as ve:
            logging.error(f"Invalid input: {str(ve)}")
            raise
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            raise

    @staticmethod
    def insert_quiz_question(questions: List[QuizQuestion]) -> None:
        graphAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])
        
        query = """
        UNWIND $questions AS q
        CREATE (question:QuizQuestion {
            id: q.questionId,
            userId: q.userId,
            courseId: q.courseId,
            noteId: q.noteId,
            quizId: q.quizId,
            question: q.question,
            answers: q.answers,
            topics: q.topics,
            difficulty: q.difficulty
        })

        RETURN q
        """

        params = {'questions': [
            {
                'questionId': q.questionId,
                'quizId': q.quizId,
                'userId': q.userId,
                'courseId': q.courseId,
                'noteId': q.noteId,
                'question': q.question,
                'answers': json.dumps([{ ## When getting answers, need to do json.loads()
                    'label': a.label,
                    'correct': a.correct,
                    'explanation': a.explanation
                } for a in q.answers]),
                'topics': q.topics,
                'difficulty': q.difficulty
            } for q in questions
        ]}
        
        graphAccess.execute_query(query, params)