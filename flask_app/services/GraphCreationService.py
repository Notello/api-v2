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
from flask_app.src.shared.common_fn import get_graph

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

            try:
                similar = similarityService.same_youtube_node_exists(course_id=courseId, url=sourceUrl)
            except Exception as e:
                logging.exception(f'Exception in same_youtube_node_exists: {e}')
                SupabaseService.update_note(noteId=noteId, key='contentStatus', value='error')
                raise e

            if similar:
                logging.info(f"File: {sourceUrl} is similar to {similar}")
                SupabaseService.update_note(
                    noteId=noteId,
                    key='matchingNoteId',
                    value=similar
                )
                SupabaseService.update_note(
                    noteId=noteId, 
                    key='graphStatus', 
                    value='complete'
                    )
                SupabaseService.update_note(
                    noteId=noteId, 
                    key='contentStatus',
                    value='complete'
                    )
                return
            
            transcript = HelperService.check_url_source(ytUrl=sourceUrl)

            SupabaseService.update_note(noteId=noteId, key='sourceUrl', value=sourceUrl)
            SupabaseService.update_note(noteId=noteId, key='contentStatus', value='complete')

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
            
            graphDb_data_Access: graphDBdataAccess = graphDBdataAccess(get_graph())

            fileName, pages = get_documents_from_youtube(obj_source_node.url)

            obj_source_node.noteId = noteId

            graphDb_data_Access.create_source_node(obj_source_node)

            processing_source(
                graphDb_data_Access=graphDb_data_Access,
                fileName=fileName,
                pages=pages,
                userId=userId,
                courseId=courseId,
                noteId=noteId
                )
            
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

            """
            IF FOUND SIMILAR DOC, GET NOTEID FOR IT AND UPDATE ALL NODES WITH THAT NOTEID TO INCLUDE THIS NOTEID
            """

            similar = similarityService.has_similar_documents(
                courseId=courseId,
                noteId=noteId,
                documents=pages
            )

            if similar:
                logging.info(f"File: {fileName} is similar to {similar}")
                SupabaseService.update_note(
                    noteId=noteId,
                    key='matchingNoteId',
                    value=similar
                )
                SupabaseService.update_note(
                    noteId=noteId, 
                    key='graphStatus', 
                    value='complete'
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

            graphDb_data_Access: graphDBdataAccess = graphDBdataAccess(get_graph())

            obj_source_node.noteId = noteId

            graphDb_data_Access.create_source_node(obj_source_node)

            processing_source(
                graphDb_data_Access=graphDb_data_Access,
                fileName=fileName,
                pages=pages,
                userId=userId,
                courseId=courseId,
                noteId=noteId
                )
            
            logging.info(f'File {fileName} has been processed successfully, success_count: {successCount}, failed_count: {failedCount}')
        except Exception as e:
            logging.exception(f'Exception: {e}')
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')

    @staticmethod
    def insert_quiz_question(questions: List[QuizQuestion]) -> None:
        graphAccess = graphDBdataAccess(get_graph())
        
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
            chunkIds: q.chunkIds,
            difficulty: q.difficulty
        })
        
        WITH question, q
        UNWIND q.topics AS topicId
        MATCH (concept:Concept {id: topicId})
        CREATE (concept)-[:HAS_QUESTION]->(question)
        
        WITH question, q
        UNWIND q.chunkIds AS chunkId
        MATCH (chunk:Chunk {id: chunkId})
        CREATE (chunk)-[:HAS_QUESTION]->(question)
        
        RETURN q
        """

        params = {'questions': [
            {
                'questionId': q['questionId'],
                'quizId': q['quizId'],
                'userId': q['userId'],
                'courseId': q['courseId'],
                'noteId': q['noteId'] if q['noteId'] != [None] else "None",
                'question': q['question'],
                'difficulty': q['difficulty'],
                'answers': json.dumps([{  # When getting answers, need to do json.loads()
                    'label': a['label'],
                    'correct': a['correct'],
                    'explanation': a['explanation']
                } for a in q['answers']]),
                'chunkIds': q['chunkIds'],
                'topics': q['topics'],
            } for q in questions
        ]}

        print(params)
        print(query)
        
        graphAccess.execute_query(query, params)

    def insert_summaries(summaries: List[Dict[str, str]]) -> None:
        graphAccess = graphDBdataAccess(get_graph())
        
        query = """
        UNWIND $summaries AS s
        CREATE (summary:Summary {
            userId: s.userId,
            courseId: s.courseId,
            noteId: s.noteId,
            content: s.content,
            concept: s.concept,
            topicId: s.topicId
        })

        WITH summary, s
        MATCH (concept:Concept)
        WHERE s.topicId IN concept.uuid
        CREATE (concept)-[:HAS_SUMMARY]->(summary)
        
        RETURN s
        """

        params = {'summaries': [
            {
                'userId': s['userId'],
                'courseId': s['courseId'],
                'noteId': s['noteId'],
                'content': s['content'],
                'concept': s['concept'],
                'topicId': s['topicId'],
            } for s in summaries
        ]}

        graphAccess.execute_query(query, params)