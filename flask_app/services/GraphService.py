from datetime import datetime
import sys
import logging
from typing import Dict, List, Tuple
from flask import current_app
from .SupabaseService import SupabaseService
from langchain_core.documents import Document
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.entities.source_node import sourceNode
from flask_app.src.document_sources.youtube import get_documents_from_youtube
from flask_app.src.main import processing_source
from flask_app.src.document_sources.text_loader import get_text_chunks_langchain
from .HelperService import HelperService
from .SimilarityService import SimilarityService




class GraphService:
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
            
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='complete')

            # graphDb_data_Access.update_KNN_graph()

            logging.info(f'File {fileName} has been processed successfully, success_count: {successCount}, failed_count: {failedCount}')
        except Exception as e:
            logging.exception(f'Exception: {e}')
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')

    @staticmethod
    def get_graph_for_param(key: str, value: str) -> Tuple[Dict[str, List[Dict]], List[Tuple[int, str, int]]]:
        try:
            graphDb_data_Access = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

            QUERY = f"""
            MATCH (n)
            WHERE n.{key} = $value OR $value IN n.{key}
            OPTIONAL MATCH (n)-[r]->(relatedNode)
            WHERE relatedNode.{key} = $value or $value IN relatedNode.{key}
            RETURN ID(n) AS nodeId, LABELS(n) AS nodeLabels, 
                n.fileName AS fileName, n.position AS position, n.id AS conceptId, n.description AS description,
                r.type AS relType, ID(relatedNode) AS relatedNodeId, LABELS(relatedNode) AS relatedNodeLabels,
                relatedNode.fileName AS relatedNodeFileName, relatedNode.position AS relatedNodePosition, 
                relatedNode.id AS relatedNodeConceptId, relatedNode.description AS relatedNodeDescription
            """

            parameters = {
                "value": value
            }

            result = graphDb_data_Access.execute_query(QUERY, parameters)

            nodes = {
                'documents': [],
                'chunks': [],
                'concepts': []
            }
            relationships = []

            for record in result:
                node_id = record.get('nodeId')
                node_labels = record.get('nodeLabels')
                file_name = record.get('fileName')
                position = record.get('position')
                concept_id = record.get('conceptId')
                description = record.get('description')

                related_node_id = record.get('relatedNodeId')
                related_node_labels = record.get('relatedNodeLabels')
                related_file_name = record.get('relatedNodeFileName')
                related_position = record.get('relatedNodePosition')
                related_concept_id = record.get('relatedNodeConceptId')
                related_description = record.get('relatedNodeDescription')

                rel_type = record.get('relType')

                if node_id is not None and node_labels:
                    if 'Document' in node_labels:
                        nodes['documents'].append({
                            'id': node_id, 
                            'fileName': file_name
                        })
                    elif 'Chunk' in node_labels:
                        nodes['chunks'].append({
                            'id': node_id, 
                            'position': position
                        })
                    elif 'Concept' in node_labels:
                        nodes['concepts'].append({
                            'id': node_id, 
                            'conceptId': concept_id, 
                            'description': description
                        })

                if related_node_id is not None and related_node_labels:
                    if 'Document' in related_node_labels:
                        nodes['documents'].append({
                            'id': related_node_id, 
                            'fileName': related_file_name
                            })
                    elif 'Chunk' in related_node_labels:
                        nodes['chunks'].append({
                            'id': related_node_id, 
                            'position': related_position
                            })
                    elif 'Concept' in related_node_labels:
                        nodes['concepts'].append({
                            'id': related_node_id,
                            'conceptId': related_concept_id, 
                            'description': related_description
                            })

                if node_id is not None and related_node_id is not None and rel_type is not None:
                    relationships.append({
                        "start_node_id": node_id, 
                        "relationship_type": rel_type, 
                        "end_node_id": related_node_id
                    })

            # Ensure unique nodes by their attributes
            nodes['documents'] = [dict(t) for t in {tuple(d.items()) for d in nodes['documents']}]
            nodes['chunks'] = [dict(t) for t in {tuple(d.items()) for d in nodes['chunks']}]
            nodes['concepts'] = [dict(t) for t in {tuple(d.items()) for d in nodes['concepts']}]

            print(len(nodes['documents']), len(nodes['chunks']), len(nodes['concepts']))

            return nodes, relationships

        except Exception as e:
            logging.error(f"Error executing query: {e.with_traceback()}")
            return None, None