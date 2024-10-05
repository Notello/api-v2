import logging
import os
from typing import Dict, List
from langchain.docstore.document import Document
from supabase import Client, create_client

from flask_app.constants import CHUNK_TABLE_NAME, COURSEID, NOTE_TOPIC_TABLE_NAME, TOPIC_TABLE_NAME, TOPIC_RELATIONSHIP_TABLE_NAME, CHUNK_TOPIC_TABLE_NAME
from flask_app.src.shared.common_fn import load_embedding_model
from flask_app.services.HelperService import HelperService

supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

class SupaGraphService():
    @staticmethod
    def insert_chunk(
        noteId, 
        courseId, 
        chunk: Document,
    ):
        embeddings, dimension = load_embedding_model()

        output = supabase.table(CHUNK_TABLE_NAME).insert({
            'noteId': str(noteId),
            'courseId': str(courseId),
            'offset': chunk.metadata.get("start"),
            'embedding': embeddings.embed_query(text=chunk.page_content),
            'content': chunk.page_content,
        }).execute().data

        if not output:
            return None

        return output[0]['id']
    
    @staticmethod
    def insert_topics(
        graph_document,
        noteId
    ):
        logging.info(f"#############################################Inserting topics for graph document")

        logging.info(f"Graph document: {graph_document}")

        nodes = [{'id': node['uuid'][0], 'name': node['id'], 'courseId': node[COURSEID][0]} for node in graph_document['nodes']]

        logging.info(f"rels: {graph_document['relationships']}")

        if nodes:
            res = supabase.table(TOPIC_TABLE_NAME).insert(nodes).execute().data

            logging.info(f"Inserted {len(nodes)} nodes for topic table")

            if not res:
                logging.info(f"Failed to insert nodes for topic table")
                return None
            
        rels = [{'topicId': rel['source_uuid'][0], 'relatedTopicId': rel['target_uuid'][0], 'type': rel['type'], 'noteId': noteId} for rel in graph_document['relationships']]
        
        logging.info(f"rels: {rels}, graph_document: {graph_document}")

        if rels:

            supabase.table(TOPIC_RELATIONSHIP_TABLE_NAME).insert(rels).execute().data

            if not res:
                logging.info(f"Failed to insert relationships for topic table")
                return None
        
        return nodes
    
    @staticmethod
    def connect_topics(
        nodes,
        chunk_id,
        noteId
    ):
        supabase.table(CHUNK_TOPIC_TABLE_NAME).insert([{'chunkId': chunk_id, 'topicId': node['id']} for node in nodes]).execute().data

    @staticmethod
    def merge_similar_nodes(
        courseId
    ):
        topics = supabase.table(TOPIC_TABLE_NAME).select("*").eq("courseId", courseId).execute().data

        root_map: Dict[str, List] = {}
        finalTopics = []

        for topic in topics:
            node_id = topic['name']
            node_id = HelperService.get_cleaned_id(node_id)

            if node_id not in root_map:
                root_map[node_id] = topic['id']

            topic['name'] = node_id
            topic['mergedId'] = root_map[node_id]
            finalTopics.append(topic)

        logging.info(f"Final topics: {finalTopics}")
        
        res = supabase.table(TOPIC_TABLE_NAME).upsert(finalTopics).execute().data

        logging.info(f"Merged topics: {res}")

    @staticmethod
    def update_embeddings(courseId: str):
        embedding, dimension = load_embedding_model()

        topics = supabase.table(TOPIC_TABLE_NAME) \
            .select("*") \
            .eq("courseId", courseId) \
            .is_("embedding", "null") \
            .execute() \
            .data
        
        for topic in topics:
            logging.info(f"Updating embedding for topic: {topic}")
            topic['embedding'] = embedding.embed_query(text=topic['name'])

        supabase.table(TOPIC_TABLE_NAME).upsert(topics).execute()
