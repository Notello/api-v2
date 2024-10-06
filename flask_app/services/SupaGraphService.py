import logging
import os
from typing import Dict, List
import asyncio
from langchain.docstore.document import Document
from supabase import Client, create_client
import numpy as np
import ast

from flask_app.constants import CHUNK_TABLE_NAME, COURSEID, ID, NOTE_TABLE_NAME, NOTE_TOPIC_TABLE_NAME, NOTEID, TOPIC_SUMMARY_TABLE_NAME, TOPIC_TABLE_NAME, TOPIC_RELATIONSHIP_TABLE_NAME, CHUNK_TOPIC_TABLE_NAME
from flask_app.src.shared.common_fn import load_embedding_model
from flask_app.services.HelperService import HelperService

supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

class SupaGraphService():
    @staticmethod
    def insert_chunk(
        noteId, 
        courseId, 
        chunk: Document,
        document_name
    ):
        embeddings, dimension = load_embedding_model()

        output = supabase.table(CHUNK_TABLE_NAME).insert({
            'noteId': str(noteId),
            'courseId': str(courseId),
            'offset': chunk.metadata.get("start"),
            'embedding': embeddings.embed_query(text=chunk.page_content),
            'content': chunk.page_content,
            'document_name': document_name,
        }).execute().data

        if not output:
            return None

        return output[0]['id']
    
    @staticmethod
    def insert_topics(
        graph_document,
        noteId,
        courseId
    ):
        nodes = [{'id': node['uuid'][0], 'name': node['id'], 'courseId': node[COURSEID][0]} for node in graph_document['nodes']]


        if nodes:
            res = supabase.table(TOPIC_TABLE_NAME).insert(nodes).execute().data

            logging.info(f"Inserted {len(nodes)} nodes for topic table")

            if not res:
                logging.info(f"Failed to insert nodes for topic table")
                return None
            
        rels = [{
            'topicId': rel['source_uuid'][0], 
            'relatedTopicId': rel['target_uuid'][0], 
            'type': rel['type'], 
            'noteId': noteId,
            'courseId': courseId
            } for rel in graph_document['relationships']]
        

        if rels:

            supabase.table(TOPIC_RELATIONSHIP_TABLE_NAME).insert(rels).execute().data

            if not res:
                logging.info(f"Failed to insert relationships for topic table")
                return None
        
        return graph_document['nodes']
    
    @staticmethod
    def connect_topics(
        nodes,
        chunk_id,
        noteId
    ):
        supabase.table(CHUNK_TOPIC_TABLE_NAME).insert([
            {
                'chunkId': chunk_id, 
                'topicId': node['uuid'][0],
                'description': node['description']
            } for node in nodes]).execute().data

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

        
        supabase.table(TOPIC_TABLE_NAME).upsert(finalTopics).execute()

    @staticmethod
    async def update_topic_embedding(topic: Dict, embedding) -> Dict:
        loop = asyncio.get_event_loop()
        topic['embedding'] = await loop.run_in_executor(None, embedding.embed_query, topic['name'])
        return topic

    @staticmethod
    async def update_embeddings_async(courseId: str, embedding):
        topics = supabase.table(TOPIC_TABLE_NAME) \
            .select("*") \
            .eq("courseId", courseId) \
            .is_("embedding", "null") \
            .execute() \
            .data

        tasks = [SupaGraphService.update_topic_embedding(topic, embedding) for topic in topics]
        updated_topics = await asyncio.gather(*tasks)

        supabase.table(TOPIC_TABLE_NAME).upsert(updated_topics).execute()

    @staticmethod
    def update_embeddings(courseId: str):
        embedding, dimension = load_embedding_model()

        asyncio.run(SupaGraphService.update_embeddings_async(courseId, embedding))

    @staticmethod
    def get_meta_context(param: str, id: str):
        param_map = {
            NOTEID: "id",
            COURSEID: "courseId",
        }
        notes = supabase.table(NOTE_TABLE_NAME).select("*").eq(param_map[param], str(id)).execute().data
        chunks = supabase.table(CHUNK_TABLE_NAME).select("*").eq(param, str(id)).execute().data
        
        topics = SupaGraphService.get_topics_for_param(param=param, id=id)
        
        summaries = [note['summary'] for note in notes[:10]]
        
        chunks_formatted = [{"text": chunk['content'], "noteId": chunk['noteId']} for chunk in chunks[:10]]
        
        topic_groups = {}
        for topic in topics:
            merged_id = topic.get('mergedId', topic['id'])
            if merged_id not in topic_groups:
                topic_groups[merged_id] = []
            topic_groups[merged_id].append(topic)
        
        sorted_groups = sorted(topic_groups.items(), key=lambda x: len(x[1]), reverse=True)
        top_25_groups = sorted_groups[:25]
        
        grouped_topics = [
            {
                "name": group[0]['name'],
                "rel_count": len(group)
            }
            for merged_id, group in top_25_groups
        ]

        return {
            "summaries": summaries,
            "chunks": chunks_formatted,
            "concepts": grouped_topics
        }
    
    @staticmethod
    def get_context(
        param: str, 
        id: str,
        query_str: str, 
        entities, 
        num_chunks: int, 
        num_related_concepts: int,
        ):

        context_nodes = {}

        for entity in entities:
            logging.info(f"Entity: {entity}")
            similar_topic = SupaGraphService.get_most_similar_topic(
                topic_name=entity, 
                param=param,
                id=id
                )
            
            if similar_topic:
                output = SupaGraphService.get_topic_context(
                    topicId=similar_topic['id'], 
                    num_chunks=num_chunks, 
                    num_related_concepts=num_related_concepts,
                    param=param,
                    id=id
                    )
                
                if not output:
                    return []
                
                context_nodes[similar_topic['id']] = output
        
        if not context_nodes:
            similar_topic = SupaGraphService.get_most_similar_topic(
                topic_name=query_str, 
                param=param,
                id=id
                )
            
            if not similar_topic:
                return []
            
            output = SupaGraphService.get_topic_context(
                topicId=similar_topic['id'],
                num_chunks=num_chunks * 2,
                num_related_concepts=num_related_concepts,
                param=param, 
                id=id
                )
            
            if not output:
                return []
            
            context_nodes[similar_topic['id']] = output
        
        print(context_nodes)
        
        return context_nodes
                

    @staticmethod
    def get_most_similar_topic(topic_name, param, id):
        embeddings, dimension = load_embedding_model()

        topic_embedding = np.array(embeddings.embed_query(text=topic_name))

        topic_embedding = topic_embedding.flatten()

        topics = SupaGraphService.get_topics_for_param(param=param, id=id)

        all_embeddings = np.array([ast.literal_eval(topic['embedding']) for topic in topics])

        similarities = np.dot(all_embeddings, topic_embedding) / (
            np.linalg.norm(all_embeddings, axis=1) * np.linalg.norm(topic_embedding)
        )

        most_similar_index = np.argmax(similarities)

        return topics[most_similar_index]
    
    @staticmethod
    def get_topics_for_param(param: str, id: str) -> List[str] | None:
        if not HelperService.validate_all_uuid4(id):
            logging.error(f"Invalid {param} id: {id}")
            return []
        topicRels = supabase.table(TOPIC_RELATIONSHIP_TABLE_NAME).select("*").eq(param, str(id)).execute().data
        
        topicIds = set()
        for rel in topicRels:
            topicIds.add(rel['topicId'])
            topicIds.add(rel['relatedTopicId'])
        
        topics = supabase.table(TOPIC_TABLE_NAME).select("*").in_('id', list(topicIds)).execute().data

        return topics
    
    @staticmethod
    def get_topic_context(topicId: str, num_chunks: int, num_related_concepts: int, param: str, id: str):
        if not HelperService.validate_all_uuid4(topicId):
            logging.error(f"Invalid topicId: {topicId}")
            return None
        
        relatedTopicsIds = supabase.table(TOPIC_RELATIONSHIP_TABLE_NAME).select("*").or_(f"topicId.eq.{topicId},relatedTopicId.eq.{topicId},{param}.eq.{id}").execute().data

        relatedTopicsSet = {}
        for rel in relatedTopicsIds:
            relatedTopicsSet[rel['topicId']] = rel['type']
            relatedTopicsSet[rel['relatedTopicId']] = rel['type']

        topics = SupaGraphService.get_topics_for_param(param=param, id=id)

        allRelatedTopics = []
        mainTopic = None

        for topic in topics:
            if topic['id'] == topicId:
                mainTopic = topic
            elif topic['id'] in relatedTopicsSet:
                allRelatedTopics.append({'topic': topic, 'type': relatedTopicsSet[topic['id']]})

        relatedTopics = [{
            'uuid': topic['topic']['id'],
            'id': topic['topic']['name'],
            'relation_type': topic['type']
        } for topic in allRelatedTopics[:num_related_concepts]]

        allChunks = supabase.table(CHUNK_TABLE_NAME).select("*").eq(param, str(id)).execute().data

        chunks = [{
            'document_name': chunk['document_name'],
            'text': chunk['content'],
            'id': chunk['noteId'],
            'offset': chunk['offset'],
            'noteId': chunk['noteId']
        } for chunk in allChunks[:num_chunks]]

        return {
            'start_concept': {
                'uuid': topicId,
                'id': mainTopic['name'],
            },
            'related_chunks': chunks,
            'related_concepts': relatedTopics
        }
    
    @staticmethod
    def get_graph_for_param(param: str, id: str):
        if not HelperService.validate_all_uuid4(id):
            logging.error(f"Invalid {param} id: {id}")
            return None
        
        topics = SupaGraphService.get_topics_for_param(param=param, id=id)
        
        relationships = supabase.table(TOPIC_RELATIONSHIP_TABLE_NAME).select("*").eq(param, str(id)).execute().data
        
        return {
            'topics': topics,
            'relationships': relationships
        }
    
    @staticmethod
    def update_topics(topics):
        supabase.table(TOPIC_TABLE_NAME).upsert(topics).execute()

    @staticmethod
    def insert_summary(summary: str, topicId: str, noteId, courseId):
        supabase.table(TOPIC_SUMMARY_TABLE_NAME).insert({
            'topicId': str(topicId),
            'text': summary
        })

    @staticmethod
    def get_top_topics(param: str, id: str, limit: int = 10):
        if not HelperService.validate_all_uuid4(id):
            logging.error(f"Invalid {param} id: {id}")
            return []

        relationships = supabase.table(TOPIC_RELATIONSHIP_TABLE_NAME).select("*").eq(param, str(id)).execute().data

        topics = SupaGraphService.get_topics_for_param(param=param, id=id)

        topic_map = {topic['id']: topic.get('mergedId', topic['id']) for topic in topics}

        topic_counts = {}
        for rel in relationships:
            source_id = topic_map.get(rel['topicId'], rel['topicId'])
            target_id = topic_map.get(rel['relatedTopicId'], rel['relatedTopicId'])
            
            topic_counts[source_id] = topic_counts.get(source_id, 0) + 1
            topic_counts[target_id] = topic_counts.get(target_id, 0) + 1

        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        result = []
        for topic_id, count in top_topics:
            topic_info = next((topic for topic in topics if topic['id'] == topic_id or topic.get('mergedId') == topic_id), None)
            if topic_info:
                result.append({
                    'id': topic_id,
                    'name': topic_info['name'],
                    'count': count
                })

        return result