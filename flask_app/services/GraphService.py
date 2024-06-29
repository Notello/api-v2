from datetime import datetime
import sys
import logging
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
                file_name=fileName, 
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
    def get_graph_for_param(key: str, value: str) -> None:
        try:
            graphDb_data_Access = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

            # Query to get unique nodes including node IDs with limited recursion depth
            QUERY_NODES = f"""
            MATCH (d:Document {{{key}: $value}})
            OPTIONAL MATCH (d)-[:PART_OF]-(c:Chunk)
            OPTIONAL MATCH (c)-[:HAS_ENTITY]->(e)
            OPTIONAL MATCH (e)-[*1..3]-(relatedNode)
            RETURN DISTINCT ID(d) as node_id, 'Document' as node_type, d as node
            UNION
            MATCH (d:Document {{{key}: $value}})-[:PART_OF]-(c:Chunk)
            RETURN DISTINCT ID(c) as node_id, 'Chunk' as node_type, c as node
            UNION
            MATCH (d:Document {{{key}: $value}})-[:PART_OF]-(c:Chunk)-[:HAS_ENTITY]->(e)
            RETURN DISTINCT ID(e) as node_id, 'Entity' as node_type, e as node
            UNION
            MATCH (d:Document {{{key}: $value}})-[:PART_OF]-(c:Chunk)-[:HAS_ENTITY]->(e)-[*1..3]-(relatedNode)
            WHERE NOT (relatedNode:Document OR relatedNode:Chunk)
            RETURN DISTINCT ID(relatedNode) as node_id, LABELS(relatedNode)[0] as node_type, relatedNode as node
            """

            # Query to get relationships between Document, Chunk, and Entity nodes and their related nodes with limited depth
            QUERY_RELATIONSHIPS = f"""
            MATCH (d:Document {{{key}: $value}})-[r:PART_OF]-(c:Chunk)
            RETURN DISTINCT ID(d) AS start_node_id, ID(c) AS end_node_id, type(r) AS relationship_type
            UNION
            MATCH (d:Document {{{key}: $value}})-[:PART_OF]-(c:Chunk)-[r:HAS_ENTITY]->(e)
            RETURN DISTINCT ID(c) AS start_node_id, ID(e) AS end_node_id, type(r) AS relationship_type
            UNION
            MATCH (e)-[r]->(e2)
            WHERE NOT (e:Document OR e:Chunk OR e2:Document OR e2:Chunk) AND e2 IS NOT NULL
            RETURN DISTINCT ID(e) AS start_node_id, ID(e2) AS end_node_id, type(r) AS relationship_type
            """

            parameters = {
                "value": value
            }

            # Execute queries
            nodes = graphDb_data_Access.execute_query(QUERY_NODES, parameters)
            relationships = graphDb_data_Access.execute_query(QUERY_RELATIONSHIPS, parameters)

            # Initialize lists for categorized nodes
            document_nodes = []
            chunk_nodes = []
            entity_nodes = []

            # Convert timestamps to strings and categorize nodes
            node_ids = set()  # Set to keep track of all node IDs
            for node in nodes:
                if "created_at" in node['node']:
                    node['node']['created_at'] = str(node['node']['created_at'])
                if "createdAt" in node['node']:
                    node['node']['createdAt'] = str(node['node']['createdAt'])
                if "updated_at" in node['node']:
                    node['node']['updated_at'] = str(node['node']['updated_at'])
                if "updatedAt" in node['node']:
                    node['node']['updatedAt'] = str(node['node']['updatedAt'])
                if "processingTime" in node['node']:
                    node['node']['processing_time'] = str(node['node']['processing_time'])
                if "processingTime" in node['node']:
                    node['node']['processingTime'] = str(node['node']['processingTime'])

                # Add node ID to set
                node_ids.add(node['node_id'])

                # Categorize nodes
                if node['node_type'] == 'Document':
                    document_nodes.append(node)
                elif node['node_type'] == 'Chunk':
                    chunk_nodes.append(node)
                else:
                    entity_nodes.append(node)

            categorized_nodes = {
                "documents": document_nodes,
                "chunks": chunk_nodes,
                "entities": entity_nodes
            }

            # Filter relationships to only include those where both node IDs exist in the node set
            filtered_relationships = []
            seen_relationships = set()
            for rel in relationships:
                start_node_id = rel["start_node_id"]
                end_node_id = rel["end_node_id"]
                relationship_type = rel["relationship_type"]
                if start_node_id in node_ids and end_node_id in node_ids:
                    relationship_key = (start_node_id, end_node_id)
                    if relationship_key not in seen_relationships:
                        seen_relationships.add(relationship_key)
                        filtered_relationships.append({
                            "start_node_id": start_node_id,
                            "end_node_id": end_node_id,
                            "relationship_type": relationship_type
                        })

            return categorized_nodes, filtered_relationships

        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None, None