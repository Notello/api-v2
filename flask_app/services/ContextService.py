from enum import Enum
import logging
from typing import Dict, List
from flask_app.services.EntityExtractionService import EntityExtractor, SimilarTopics
from langchain_core.pydantic_v1 import BaseModel, Field
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.constants import GPT_4O_MINI
from langchain_core.pydantic_v1 import BaseModel, Field
from flask_app.src.shared.common_fn import get_llm
from langchain_core.prompts import ChatPromptTemplate
from flask_app.services.Neo4jConnection import Neo4jConnection

class QuestionType(str, Enum):
    META_GENERAL = "meta_general"
    FACT_BASED = "fact_based"
    PROBLEM_SOLVING = "problem_solving"
    EXPLORE = "explore"

class QuestionModel(BaseModel):
    question_type: QuestionType = Field(
        description="The type of question the user is asking."
    )


class ContextService():
    @staticmethod
    def get_context_nodes(question_type, query_str, history, param, id):
        logging.info(f"question_type   si: {question_type}")
        if question_type == QuestionType.META_GENERAL:
            return ContextService.get_meta_context(
                query_str=query_str, 
                history=history,
                param=param,
                id=id,
                question_type=question_type
            )
        elif question_type == QuestionType.FACT_BASED:
            return ContextService.get_context(
                query_str=query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history),
                num_chunks=15,
                num_related_concepts=10,
                param=param,
                id=id
            )
        elif question_type == QuestionType.PROBLEM_SOLVING:
            return ContextService.get_context(
                query_str=query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history),
                num_chunks=10,
                num_related_concepts=10,
                param=param,
                id=id
            )
        elif question_type == QuestionType.EXPLORE:
            return ContextService.get_context(
                query_str=query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history),
                num_chunks=15,
                num_related_concepts=50,
                param=param,
                id=id
            )
        else:
            return None

    @staticmethod
    def get_context(
        query_str: str, 
        entities, 
        num_chunks: int, 
        num_related_concepts: int,
        param,
        id
        ) -> Dict[str, str]:
        try:
            context_nodes = {}

            logging.info(f"Entities: {entities}")

            if entities:
                for entity in entities:
                    logging.info(f"Entity: {entity}")
                    similar_topic = GraphQueryService.get_most_similar_topic(
                        topic_name=entity, 
                        query_string=query_str,
                        param=param,
                        id=id
                        )

                    logging.info(f"Similar topic: {similar_topic}")

                    if similar_topic:
                        output = GraphQueryService.get_topic_graph_for_topic_uuid(
                            topic_uuid=similar_topic.conceptUuid, 
                            num_chunks=num_chunks, 
                            num_related_concepts=num_related_concepts,
                            param=param,
                            id=id
                            )

                        if not output:
                            logging.info(f"Not output for topic {entity}")
                            continue

                        logging.info(f"output2: {output}")

                        context_nodes[similar_topic.conceptId] = {
                            'uuid': output[0]['result']['start_concept']['uuid'],
                            'related_chunks': output[0]['result']['related_chunks'],
                            'related_concepts': output[0]['result']['related_concepts']
                        }

            if not context_nodes:
                similar_topic = GraphQueryService.get_most_similar_topic(
                    topic_name=query_str, 
                    query_string=query_str,
                    param=param,
                    id=id
                    )
                
                logging.info(f"similar topic: {similar_topic}")

                output = GraphQueryService.get_topic_graph_for_topic_uuid(
                    topic_uuid=similar_topic.conceptUuid,
                    num_chunks=num_chunks * 2,
                    num_related_concepts=num_related_concepts,
                    param=param, 
                    id=id
                )

                if not output:
                    return None

                logging.info(f"output1: {output}")

                context_nodes[similar_topic.conceptId] = {
                    'uuid': output[0]['result']['start_concept']['uuid'],
                    'related_chunks': output[0]['result']['related_chunks'],
                    'related_concepts': output[0]['result']['related_concepts']
                }

            print(context_nodes)
            
            return context_nodes
        except Exception as e:
            logging.error(f"Error getting context: {e}")
            return None
        
    @staticmethod
    def get_meta_context(
        query_str: str, 
        history: List[str],
        param: str,
        id: str,
        question_type: QuestionType
    ) -> Dict: 
        logging.info(f"get_meta_context")
        QUERY = f"""
        MATCH (d:Document)
        WHERE '{id}' IN d.{param}
        WITH d
        ORDER BY rand()
        LIMIT 10

        OPTIONAL MATCH (d)-[:HAS_DOCUMENT]-(c:Chunk)
        WITH d, c, rand() AS r
        ORDER BY d, r
        WITH d, head(collect(c)) AS c

        WITH collect(d.summary) AS summaries, collect({{text: c.text, noteId: c.noteId}}) AS chunks

        MATCH (concept1:Concept)-[r:RELATED]->(concept2:Concept)
        WHERE '{id}' IN concept1.{param}
        AND '{id}' IN concept2.{param}
        WITH summaries, chunks, concept1, count(r) AS rel_count
        ORDER BY rel_count DESC
        LIMIT 25

        WITH summaries, chunks, collect({{name: concept1.id, rel_count: rel_count}}) AS concepts

        RETURN {{
            summaries: summaries,
            chunks: chunks,
            concepts: concepts
        }} AS result
        """

        results = Neo4jConnection.run_query(QUERY)

        logging.info(f"results: {results}")

        return results[0]["result"] if results else None