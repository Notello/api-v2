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
from langchain_community.document_loaders import PyMuPDFLoader
from neo4j.time import DateTime





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

            obj_source_node.fileName = fileName

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

            pages = get_text_chunks_langchain(rawText)

            obj_source_node.fileName = fileName

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

            logging.info(f'File {fileName} has been processed successfully, success_count: {successCount}, failed_count: {failedCount}')
        except Exception as e:
            logging.exception(f'Exception in create_source_node_graph_url_youtube: {e}')
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')

    @staticmethod
    def get_graph_for_param(key: str, value: str) -> None:
        try:
            graphDb_data_Access = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

            # Query to get unique nodes including node IDs
            QUERY_NODES = f"""
            MATCH (d:Document {{{key}: $value}})
            OPTIONAL MATCH (d)-[:PART_OF]-(c:Chunk)
            OPTIONAL MATCH (c)-[:HAS_ENTITY]->(e)
            RETURN DISTINCT ID(d) as node_id, d as node
            UNION
            MATCH (d:Document {{{key}: $value}})-[:PART_OF]-(c:Chunk)
            RETURN DISTINCT ID(c) as node_id, c as node
            UNION
            MATCH (d:Document {{{key}: $value}})-[:PART_OF]-(c:Chunk)-[:HAS_ENTITY]->(e)
            RETURN DISTINCT ID(e) as node_id, e as node
            """

            # Query to get relationships between Document, Chunk, and Entity nodes
            QUERY_RELATIONSHIPS = f"""
            MATCH (d:Document {{{key}: $value}})-[r:PART_OF]-(c:Chunk)
            RETURN ID(d) AS start_node_id, ID(c) AS end_node_id, TYPE(r) AS relationship_type
            UNION
            MATCH (d:Document {{{key}: $value}})-[:PART_OF]-(c:Chunk)-[r:HAS_ENTITY]->(e)
            RETURN ID(c) AS start_node_id, ID(e) AS end_node_id, TYPE(r) AS relationship_type
            UNION
            MATCH (d:Document {{{key}: $value}})-[:PART_OF]-(c:Chunk)-[:HAS_ENTITY]->(e)-[r2]-(e2)
            WHERE NOT (e2:Document OR e2:Chunk)
            RETURN ID(e) AS start_node_id, ID(e2) AS end_node_id, TYPE(r2) AS relationship_type
            """

            parameters = {
                "value": value
            }

            # Execute queries
            nodes = graphDb_data_Access.execute_query(QUERY_NODES, parameters)
            relationships = graphDb_data_Access.execute_query(QUERY_RELATIONSHIPS, parameters)

            # Convert timestamps to strings
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

            print(nodes)

            return nodes, relationships

        except Exception as e:
            logging.error(f"Error executing query: {e}")