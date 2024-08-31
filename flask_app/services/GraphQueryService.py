import json
import logging
import random
from typing import Any, Dict, List, Tuple

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from flask_app.src.shared.common_fn import get_llm, load_embedding_model
from flask_app.constants import GPT_4O_MINI
from flask_app.src.graphDB_dataAccess import graphDBdataAccess

class TopConcept(BaseModel):
    conceptId: str = Field(
        description="The concept ID of the top topic."
    )
    conceptUuid: str = Field(
        description="The concept UUID of the top topic."
    )

class TopConcepts(BaseModel):
    top_topics: List[TopConcept] = Field(
        description="A list of the top topics for the given note summary."
    )

class GraphQueryService():
    @staticmethod
    def get_com_string(communityType: str, communityId: str) -> str:
        return f"{communityType}_{communityId}_community".replace("-", "_")

    @staticmethod
    def get_node_query(node_type: str, key: str, value: str, com_string: str) -> str:
        base_attributes = f"ID(n) AS id, LABELS(n)[0] AS labels, n.{com_string} AS communityId"
        type_specific_attributes = {
            "Document": "n.fileName AS fileName, [n.noteId] AS noteId",
            "Chunk": "n.offset AS offset, n.document_name AS noteName, [n.noteId] AS noteId",
            "Concept": "n.id AS nodeId, n.uuid[0] AS nodeUuid, n.noteId as noteId"
        }
        return f"""
        MATCH (n:{node_type})
        WHERE n.{key} = $value OR $value IN n.{key}
        RETURN {base_attributes}, {type_specific_attributes[node_type]}
        """

    @staticmethod
    def get_relationships_query(key: str, value: str) -> str:
        return f"""
        MATCH (n)-[rel]->(r)
        WHERE (n.{key} = $value OR $value IN n.{key}) AND (r.{key} = $value OR $value IN r.{key})
        RETURN ID(n) AS start_node_id, ID(r) AS end_node_id, rel.type AS relationship_type
        """

    @staticmethod
    def get_graph_for_param(key: str, value: str) -> Tuple[List[Dict], List[Dict[str, Any]]]:
        try:
            graphAccess = graphDBdataAccess()
            com_string = GraphQueryService.get_com_string(communityType=key, communityId=value)

            nodes = []
            relationships = []

            # Execute queries for each node type
            for node_type in ["Document", "Chunk", "Concept"]:
                query = GraphQueryService.get_node_query(node_type, key, value, com_string)
                result = graphAccess.execute_query(query, {"value": value})
                for record in result:
                    node_info = dict(record)
                    nodes.append(node_info)

            # Execute query for relationships
            rel_query = GraphQueryService.get_relationships_query(key, value)
            rel_result = graphAccess.execute_query(rel_query, {"value": value})
            for record in rel_result:
                relationships.append(dict(record))

            return nodes, relationships

        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None, None
        

    @staticmethod
    def get_communities_for_param(param: str, 
                                id: str, 
                                topics: List[str] = None,
                                num_communities: int = None,
                                min_node_count: int = 10
                                ) -> List[int] | None:
        
        logging.info(f"Getting communities for {param} with id {id}")

        graphAccess = graphDBdataAccess()
        com_string = GraphQueryService.get_com_string(communityType=param, communityId=id)

        parameters = {
            'value': id,
            'min_node_count': min_node_count
        }

        if len(topics) > 0:
            TOPIC_COMMUNITIES_QUERY = f"""
            MATCH (n)
            WHERE ANY(label IN labels(n) WHERE label IN ['Concept', 'Chunk']) AND $value in n.{param}
            WITH n
            WHERE ANY(topic IN {topics} WHERE n.id = topic)
            WITH n['{com_string}'] AS community_id, COUNT(n) AS node_count
            WHERE node_count >= $min_node_count
            RETURN DISTINCT community_id AS community_id
            """

            result = graphAccess.execute_query(TOPIC_COMMUNITIES_QUERY, parameters)
            communities = [community['community_id'] for community in result]
        else:
            ALL_COMMUNITIES_QUERY = f"""
            MATCH (n)
            WHERE $value in n.{param}
            WITH n['{com_string}'] AS community_id, COUNT(n) AS node_count
            WHERE community_id IS NOT NULL AND node_count >= $min_node_count
            RETURN DISTINCT community_id AS community_id
            """

            result = graphAccess.execute_query(ALL_COMMUNITIES_QUERY, parameters)
            communities = [community['community_id'] for community in result]

        logging.info(f"Query: {ALL_COMMUNITIES_QUERY if len(topics) == 0 else TOPIC_COMMUNITIES_QUERY}")
        logging.info(f"Result: {communities}")

        if num_communities is not None:
            communities = random.sample(communities, min(num_communities, len(communities)))
        
        logging.info(f"Filtered communities for {param} with id {id}: {communities}")

        return communities
    
    @staticmethod
    def get_random_topics(
        param: str, 
        id: str,
        num_topics: int = 1
    ):
        graphAccess = graphDBdataAccess()
        
        QUERY = f"""
        MATCH (c:Concept)
        WHERE '{id}' IN c.{param}
        WITH c, rand() AS r
        ORDER BY r
        LIMIT {num_topics}
        RETURN c.id AS id, c.uuid[0] AS uuid
        """
        
        result = graphAccess.execute_query(query=QUERY)
        
        if len(result) == 0:
            logging.error(f"Failed to get random topics for {param} with id {id}")
            return None
        
        return [{'id': item['id'], 'uuid': item['uuid']} for item in result]

    @staticmethod
    def get_topic_graph(
        param: str, 
        id: str, 
        num_rels: int = 5,
        topics: List[str] = [],
    ):
        if len(topics) == 0:
            random_topics = GraphQueryService.get_random_topics(param=param, id=id, num_topics=num_rels)
            if random_topics is None:
                return None
            topics = [topic['uuid'] for topic in random_topics]
        
        logging.info(f"Generating topic graph for topics {topics}")
        
        topic_graph = GraphQueryService.get_topic_graph_for_topics(topics=topics, param=param, id=id, num_rels=num_rels)
        
        logging.info(f"Topic graph for topics {topics} generated.")

        return topic_graph

    @staticmethod
    def get_topic_graph_for_topics(
        topics: List[str],
        param: str,
        id: str,
        num_rels: int = 5,
        chunks_per_rel: int = 1
    ):
        graphAccess = graphDBdataAccess()

        MAIN_QUERY = f"""
        WITH {topics} AS allTopics
        UNWIND range(0, {num_rels} - 1) AS i
        WITH allTopics[i % size(allTopics)] AS topic, i
        MATCH (start:Concept)
        WHERE topic IN start.uuid
        MATCH (start)-[rel]-(related:Concept)
        WHERE '{id}' IN related.{param}
        WITH start, rel, related, i
        ORDER BY i, rand()
        WITH DISTINCT start, rel, related
        LIMIT {num_rels}

        MATCH (chunk:Chunk)
        WHERE chunk.{param} = '{id}'
        WITH start, rel, related, chunk,
            apoc.coll.sum([
            CASE WHEN exists((chunk)-[:REFERENCES]->(start)) THEN 1 ELSE 0 END,
            CASE WHEN exists((chunk)-[:REFERENCES]->(related)) THEN 1 ELSE 0 END
            ]) AS relevance
        ORDER BY relevance DESC
        WITH start, rel, related, collect(chunk)[0..{chunks_per_rel}] AS relevantChunks

        RETURN {{
            source: start.id,
            sourceUUID: start.uuid,
            target: related.id,
            targetUUID: related.uuid,
            type: rel.type,
            chunks: [chunk IN relevantChunks | {{
                id: chunk.id,
                text: chunk.text,
                noteId: chunk.noteId,
                position: chunk.position,
                document_name: chunk.document_name
            }}]
        }} AS result
        """

        result = graphAccess.execute_query(query=MAIN_QUERY)

        logging.info(f"Len of result: {len(result)}")


        if len(result) == 0:
            logging.error(f"Failed to get topic graph for topics {topics}: {result}")
            logging.info(f"Query: {MAIN_QUERY}")
            return None
                
        return result
    
    @staticmethod
        
    @staticmethod
    def choose_most_important_topics(entities, note_description):
        entities_str = ", ".join([f"Name: {entity['conceptId']}, UUID: {entity['conceptUuid']}" for entity in entities])

        llm = get_llm(GPT_4O_MINI).with_structured_output(TopConcepts)
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are an expert concept selector tasked with identifying the most crucial concepts for summarizing a note. 
            Your goal is to select concepts that will provide a comprehensive understanding of the note's content while minimizing redundancy.

            Guidelines for topic selection:
            1. Relevance: Choose concepts that are central to the main ideas and arguments presented in the note.
            2. Breadth: Select a diverse range of concepts that cover different aspects of the note, ensuring a well-rounded summary.
            3. Depth: Prioritize concepts that delve into the core concepts rather than superficial details.
            4. Interconnectedness: Identify concepts that connect multiple ideas within the note, showcasing relationships between concepts.
            5. Uniqueness: Favor concepts that are specific to this note and distinguish it from general knowledge.
            6. Context: Consider the overall theme and purpose of the note when selecting concepts.
            7. Avoid Redundancy: Eliminate repetitive or closely related concepts to ensure efficiency in the summary.

            For each concept you will provide the conceptId, which is the name of the concept, and the conceptUuid, which is a uuid-4 identifier for the concept.
            """),
            ("user", f"Entities: {entities_str}\nNote Summary: {note_description}")
        ])

        invokable = prompt | llm

        result: TopConcepts = invokable.invoke({})

        logging.info(f"Result: {result}")

        return result.top_topics

    @staticmethod
    def get_importance_graph_by_param(param: str, id: str):
        graphAccess = graphDBdataAccess()

        # First query to get top 50 concepts
        QUERY1 = f"""
        MATCH (c:Concept)
        WHERE $id IN c.{param}
        OPTIONAL MATCH (c)-[:RELATED]->(relatedConcept:Concept)
        WITH c, COUNT(relatedConcept) AS connectionCount
        WITH c, connectionCount, connectionCount * log(1 + connectionCount) AS importanceScore
        ORDER BY importanceScore DESC
        LIMIT 50
        RETURN c.id AS conceptId, c.uuid[0] AS conceptUuid
        """

        parameters = {
            "id": id
        }

        try:
            top_concepts = graphAccess.execute_query(QUERY1, parameters)
            logging.info(f"Query 1: {QUERY1}")
            logging.info(f"Top concepts: {top_concepts}")

            NOTE_QUERY = f"""
            MATCH (n:Document)
            where '{id}' in n.{param}
            RETURN n.summary as summary
            """

            note_summaries = graphAccess.execute_query(NOTE_QUERY, parameters)

            logging.info(f"note_summaries: {note_summaries}")

            filtered_concepts = GraphQueryService.choose_most_important_topics(entities=top_concepts, note_description=note_summaries[0]['summary'])

            logging.info(f"filtered_concepts: {filtered_concepts}")

            # After processing, use the list of concepts for the second query
            concept_uuids = [concept.conceptUuid for concept in filtered_concepts]

            logging.info(f"concept_uuids: {concept_uuids}")

            QUERY2 = f"""
            UNWIND $conceptUuids AS targetUuid
            MATCH (c:Concept)
            WHERE targetUuid IN c.uuid
            WITH c, targetUuid

            // Find immediate concept neighbors of important nodes
            MATCH (c)-[:RELATED]-(neighbor:Concept)
            WHERE '{id}' IN neighbor.noteId

            // Find related chunks for the main concept
            WITH c, neighbor, targetUuid
            MATCH (chunk:Chunk)-[r:REFERENCES]->(c)
            WITH c, neighbor, chunk, targetUuid, count(DISTINCT c) AS relevanceScore
            ORDER BY relevanceScore DESC
            WITH c, neighbor, targetUuid, COLLECT({{
                id: chunk.id,
                text: chunk.text, 
                document_name: chunk.document_name,
                offset: chunk.offset,
                noteId: chunk.noteId
            }})[0..3] AS topChunks

            // Calculate connection counts for neighbors
            OPTIONAL MATCH (neighbor)-[:RELATED]->(neighborRelated:Concept)
            WITH c, neighbor, COUNT(neighborRelated) AS neighborConnectionCount, topChunks, targetUuid

            // Return the results
            RETURN DISTINCT
                c.id AS conceptId,
                targetUuid AS conceptUuid,
                COLLECT({{
                    id: neighbor.id, 
                    uuid: neighbor.uuid[0]
                }}) AS relatedConcepts,
                topChunks
            """

            parameters2 = {
                "id": id,
                "conceptUuids": concept_uuids
            }

            result = graphAccess.execute_query(QUERY2, parameters2)
            logging.info(f"Query 2: {QUERY2}")
            logging.info(f"result: {', '.join([concept['conceptId'] for concept in result])}")

            return result
        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None

    @staticmethod
    def get_topic_graph_for_topic_uuid(
        param,
        id,
        topic_uuid: str,
        num_chunks: int = 5,
        num_related_concepts: int = 3,
    ): 
        logging.info(f"Getting topic graph for topic uuid: {topic_uuid}")
        graphAccess = graphDBdataAccess()

        logging.info(f"Param: {param}, id: {id}")
        logging.info(f"Topic uuid: {topic_uuid}")

        if param and id:      
            MAIN_QUERY = f"""
                WITH $topic_uuid AS topic_uuid
                MATCH (start:Concept)
                WHERE topic_uuid IN start.uuid AND '{id}' in start.{param}

                // Find related concepts
                OPTIONAL MATCH (start)-[r1:RELATED]-(related:Concept)
                WHERE NOT topic_uuid IN related.uuid AND '{id}' in related.{param}

                // Find chunks related to the start concept
                OPTIONAL MATCH (chunk:Chunk)-[r2:REFERENCES]-(start)
                WHERE '{id}' in chunk.{param}

                // Collect results
                WITH start, 
                    COLLECT(DISTINCT {{
                        uuid: related.uuid[0],
                        id: related.id,
                        relation_type: r1.type
                    }})[..{num_related_concepts}] AS related_concepts,
                    COLLECT(DISTINCT {{
                        document_name: chunk.document_name,
                        text: chunk.text,
                        id: chunk.noteId,
                        offset: chunk.offset,
                        noteId: chunk.noteId
                    }})[..{num_chunks}] AS related_chunks

                // Return the results
                RETURN {{
                    start_concept: {{
                        uuid: start.uuid[0],
                        id: start.id
                    }},
                    related_concepts: related_concepts,
                    related_chunks: related_chunks
                }} as result
            """
        else:
            MAIN_QUERY = f"""
                WITH $topic_uuid AS topic_uuid
                MATCH (start:Concept)
                WHERE topic_uuid IN start.uuid

                // Find related concepts
                OPTIONAL MATCH (start)-[r1:RELATED]-(related:Concept)
                WHERE NOT topic_uuid IN related.uuid

                // Find chunks related to the start concept
                OPTIONAL MATCH (chunk:Chunk)-[r2:REFERENCES]-(start)

                // Collect results
                WITH start, 
                    COLLECT(DISTINCT {{
                        uuid: related.uuid[0],
                        id: related.id,
                        relation_type: r1.type
                    }})[..{num_related_concepts}] AS related_concepts,
                    COLLECT(DISTINCT {{
                        document_name: chunk.document_name,
                        text: chunk.text,
                        id: chunk.noteId,
                        offset: chunk.offset,
                        noteId: chunk.noteId
                    }})[..{num_chunks}] AS related_chunks

                // Return the results
                RETURN {{
                    start_concept: {{
                        uuid: start.uuid[0],
                        id: start.id
                    }},
                    related_concepts: related_concepts,
                    related_chunks: related_chunks
                }} as result
            """

        logging.info(f"Query: {MAIN_QUERY}")

        parameters = {
            'topic_uuid': topic_uuid
        }

        result = graphAccess.execute_query(query=MAIN_QUERY, params=parameters)

        return result
    
    @staticmethod
    def get_display_topic_graph(uuid: str, courseId: str) -> Tuple[List[Dict], List[Dict[str, Any]]] | None:
        try:
            graphAccess = graphDBdataAccess()

            com_string = GraphQueryService.get_com_string(communityType='courseId', communityId=courseId)

            node_query = f"""
            MATCH (root:Concept)
            WHERE $uuid IN root.uuid
            OPTIONAL MATCH (root)--(n1)
            WHERE n1:Document OR n1:Chunk OR n1:Concept
            OPTIONAL MATCH (n1)--(n2)
            WHERE n2:Document OR n2:Chunk OR n2:Concept
            WITH root, n1, n2
            UNWIND [root, n1, n2] AS n
            WITH n WHERE n IS NOT NULL
            RETURN DISTINCT
                CASE
                    WHEN n:Document THEN {{
                        id: ID(n),
                        labels: LABELS(n)[0],
                        fileName: n.fileName,
                        noteId: n.noteId
                    }}
                    WHEN n:Chunk THEN {{
                        id: ID(n),
                        labels: LABELS(n)[0],
                        offset: n.offset,
                        noteId: n.noteId
                    }}
                    WHEN n:Concept THEN {{
                        id: ID(n),
                        labels: LABELS(n)[0],
                        communityId: n.{com_string},
                        nodeId: n.id,
                        nodeUuid: n.uuid[0],
                        noteId: n.noteId
                    }}
                END AS node
            """

            relationship_query = f"""
            MATCH (root:Concept)
            WHERE $uuid IN root.uuid
            OPTIONAL MATCH (root)-[r1]-(n1)
            WHERE n1:Document OR n1:Chunk OR n1:Concept
            OPTIONAL MATCH (n1)-[r2]-(n2)
            WHERE n2:Document OR n2:Chunk OR n2:Concept
            UNWIND [r1, r2] AS rel
            WITH rel WHERE rel IS NOT NULL
            RETURN DISTINCT ID(startNode(rel)) AS start_node_id, ID(endNode(rel)) AS end_node_id, type(rel) AS relationship_type
            """

            node_result = graphAccess.execute_query(node_query, {"uuid": uuid})
            rel_result = graphAccess.execute_query(relationship_query, {"uuid": uuid})

            nodes = [dict(record['node']) for record in node_result if record['node'] is not None]
            relationships = [dict(record) for record in rel_result]

            return nodes, relationships

        except Exception as e:
            logging.error(f"Error executing query: {e}")
            return None

    @staticmethod
    def get_summary_for_param(param: str, id: str) -> str | None:
        graphAccess = graphDBdataAccess()

        logging.info(f"Getting summary for param {param} with id {id}")
        
        QUERY = f"""
        MATCH (n:Concept)
        WHERE $id IN n.{param}
        OPTIONAL MATCH (n)-[r:HAS_SUMMARY]->(s:Summary) 
        WHERE $id in s.{param}
        RETURN n.id AS conceptId, s
        """

        parameters = {
            'id': id
        }

        result = graphAccess.execute_query(QUERY, parameters)

        return {
            'summaries': [res.get('s') for res in result if res.get('s') is not None],
            'concept': result[0].get('conceptId') if len(result) > 0 else None
        }

    @staticmethod
    def get_topic_summary(uuid: str) -> str | None:
        graphAccess = graphDBdataAccess()

        QUERY = f"""
        Match (n:Concept)
        WHERE '{uuid}' IN n.uuid
        OPTIONAL MATCH (n)-[r:HAS_SUMMARY]->(s:Summary) 
        RETURN n.id AS conceptId, s
        """

        result = graphAccess.execute_query(QUERY)

        return {
            'summaries': [res.get('s') for res in result if res.get('s') is not None],
            'concept': result[0].get('conceptId') if len(result) > 0 else None
        }

    
    @staticmethod
    def get_topics_for_param(param: str, id: str) -> List[str] | None:
        graphAccess = graphDBdataAccess()
        
        QUERY = f"""
        MATCH (n:Concept)
        WHERE $id IN n.{param}
        RETURN n.id AS conceptId, n.uuid[0] AS conceptUuid, n.noteId AS noteId
        """

        parameters = {
            'id': id
        }

        print(f"Query: {QUERY}")
        print(f"Parameters: {parameters}")

        result = graphAccess.execute_query(QUERY, parameters)

        return result
    
    @staticmethod
    def get_num_topics_for_param(param: str, id: str) -> int | None:
        graphAccess = graphDBdataAccess()
        
        QUERY = f"""
        MATCH (n:Concept)
        WHERE $id IN n.{param}
        RETURN COUNT(n) AS num_topics
        """

        parameters = {
            'id': id
        }

        result = graphAccess.execute_query(QUERY, parameters)

        return result[0].get('num_topics') if len(result) > 0 else None


    @staticmethod
    def get_notes_for_topic(uuid: str) -> List[Dict] | None:
        graphAccess = graphDBdataAccess()
        
        QUERY = f"""
        MATCH (n:Concept)
        WHERE '{uuid}' IN n.uuid
        RETURN n.noteId AS noteId
        """

        result = graphAccess.execute_query(QUERY)

        return result
    
    @staticmethod
    def get_most_similar_topic(topic_name: str, similarity_threshold):
        graph_access = graphDBdataAccess()

        embeddings, dimension = load_embedding_model()

        topic_embedding = embeddings.embed_query(text=topic_name)

        QUERY = f"""
        CALL db.index.vector.queryNodes('concept_embedding', 20, {topic_embedding}) YIELD node AS n, score
        RETURN {{
            uuid: n.uuid[0],
            id: n.id,
            similarity: score
        }} AS result
        ORDER BY score DESC
        LIMIT 1
        """

        result = graph_access.execute_query(
            query=QUERY,
            params={"embedding": topic_embedding}
        )

        # Check if a result was found
        if result and len(result) > 0:
            return result[0]["result"]
        else:
            return None
        
    @staticmethod
    def get_flashcards(flashcardId: str) -> List[Dict] | None:
        graphAccess = graphDBdataAccess()
        
        QUERY = f"""    
        MATCH (c:Chunk)-[r:REFERENCES]->(n:Concept)
        WHERE '{flashcardId}' in r.flashcardId
        RETURN n.id as conceptId, n.uuid[0] as conceptUuid, r.description as description
        """

        result = graphAccess.execute_query(QUERY)

        return result
    
    @staticmethod
    def get_quiz_questions_by_id(quizId: str) -> List[Dict] | None:
        graphAccess = graphDBdataAccess()

        QUERY = f"""
        MATCH (q:QuizQuestion)
        WHERE '{quizId}' IN q.quizId
        RETURN q.id AS questionId, q.question AS question, q.answers AS answers, q.difficulty AS difficulty, q.topics AS topics, q.chunkIds as chunkIds
        """

        result = graphAccess.execute_query(QUERY)

        questions = []

        for record in result:
            questions.append({
                'id': record['questionId'],
                'question': record['question'],
                'answers': json.loads(record['answers']),
                'difficulty': record['difficulty'],
                'topics': record['topics'],
                'chunkIds': record['chunkIds']
            })

        return questions