from datetime import datetime
import sys
import logging
from typing import Any, Dict, List, Tuple
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
    DEFAULT_GRAPH_PARAMS = [("ID(n)", "nodeId"), ("LABELS(n)", "nodeLabels"), 
                ("n.fileName", "fileName"), ("n.position", "position"), ("n.id", "conceptId"),("n.description", "description"),
                ("r.type", "relType"), ("ID(relatedNode)", "relatedNodeId"), ("LABELS(relatedNode)", "relatedNodeLabels"),
                ("relatedNode.fileName", "relatedNodeFileName"), ("relatedNode.position", "relatedNodePosition"), 
                ("relatedNode.id", "relatedNodeConceptId"), ("relatedNode.description", "relatedNodeDescription")]

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
    def get_graph_for_param(
        key: str, 
        value: str, 
        return_params: List[Tuple[str, str]] = DEFAULT_GRAPH_PARAMS
    ) -> Tuple[Dict[str, List[Dict]], List[Dict[str, Any]]]:
        try:
            graphDb_data_Access = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

            return_clause = ", ".join([f"{param[0]} AS {param[1]}" for param in return_params])

            QUERY = f"""
            MATCH (n)
            WHERE n.{key} = $value OR $value IN n.{key}
            OPTIONAL MATCH (n)-[r]->(relatedNode)
            WHERE relatedNode.{key} = $value or $value IN relatedNode.{key}
            RETURN {return_clause}
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
                node_data = {}
                related_node_data = {}
                rel_type = None

                for param in return_params:
                    attr_name = param[1]
                    attr_value = record.get(attr_name)
                    
                    if attr_name.startswith("relatedNode"):
                        related_node_data[attr_name.replace("relatedNode", "")] = attr_value
                    elif attr_name == "relType":
                        rel_type = attr_value
                    else:
                        node_data[attr_name] = attr_value

                if 'nodeId' in node_data and 'nodeLabels' in node_data:
                    node_type = next((label for label in ['Document', 'Chunk', 'Concept'] if label in node_data['nodeLabels']), None)
                    if node_type:
                        node_info = {'id': node_data['nodeId']}
                        if node_type == 'Document':
                            node_info['fileName'] = node_data.get('fileName')
                        elif node_type == 'Chunk':
                            node_info['position'] = node_data.get('position')
                        elif node_type == 'Concept':
                            node_info['conceptId'] = node_data.get('conceptId')
                            node_info['description'] = node_data.get('description')
                        nodes[node_type.lower() + 's'].append(node_info)

                if related_node_data.get('Id') is not None and related_node_data.get('Labels') is not None:
                    related_node_type = next((label for label in ['Document', 'Chunk', 'Concept'] if label in related_node_data['Labels']), None)
                    if related_node_type:
                        related_node_info = {'id': related_node_data['Id']}
                        if related_node_type == 'Document':
                            related_node_info['fileName'] = related_node_data.get('FileName')
                        elif related_node_type == 'Chunk':
                            related_node_info['position'] = related_node_data.get('Position')
                        elif related_node_type == 'Concept':
                            related_node_info['conceptId'] = related_node_data.get('ConceptId')
                            related_node_info['description'] = related_node_data.get('Description')
                        nodes[related_node_type.lower() + 's'].append(related_node_info)

                if 'nodeId' in node_data and related_node_data.get('Id') is not None and rel_type is not None:
                    relationships.append({
                        "start_node_id": node_data['nodeId'], 
                        "relationship_type": rel_type, 
                        "end_node_id": related_node_data['Id']
                    })

            # Ensure unique nodes by their attributes
            for node_type in nodes:
                nodes[node_type] = [dict(t) for t in {tuple(d.items()) for d in nodes[node_type]}]

            return nodes, relationships

        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None, None