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

class QuestionType(str, Enum):
    EXPLORE = "explore"
    ANSWER = "answer"
    RELATIONSHIP = "relationship"
    FOLLOWUP = "followup"

class BotPrompt(str, Enum):
    DEFAULT = "default"
    MATH = "math"
    SCIENCE = "science"

class QuestionModel(BaseModel):
    question_type: QuestionType = Field(
        description="The type of question the user is asking."
    )
    answer_format: BotPrompt = Field(
        description="The format of the bot's response."
    )

class ContextService():
    @staticmethod
    def get_context_nodes(question_type, query_str, history, param, id):
        if question_type == QuestionType.EXPLORE:
            return ContextService.get_context(
                query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history), 
                num_chunks=3, 
                num_related_concepts=25,
                param=param,
                id=id
                )
        elif question_type == QuestionType.ANSWER:
            return ContextService.get_context(
                query_str=query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history), 
                num_chunks=7, 
                num_related_concepts=25,
                param=param,
                id=id
                )
        elif question_type == QuestionType.RELATIONSHIP:
            return ContextService.get_context(
                query_str=query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history), 
                num_chunks=3, 
                num_related_concepts=100,
                param=param,
                id=id
                )
        elif question_type == QuestionType.FOLLOWUP:
            return ContextService.get_context(
                query_str=query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history), 
                num_chunks=3, 
                num_related_concepts=25,
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
                    similar_topic = GraphQueryService.get_most_similar_topic(topic_name=entity, similarity_threshold=0.97)

                    logging.info(f"Similar topic: {similar_topic}")

                    if similar_topic:
                        output = GraphQueryService.get_topic_graph_for_topic_uuid(
                            topic_uuid=similar_topic['uuid'], 
                            num_chunks=num_chunks, 
                            num_related_concepts=num_related_concepts,
                            param=param,
                            id=id
                            )

                        if not output:
                            logging.info(f"Not output for topic {entity}")
                            continue

                        context_nodes[similar_topic['id']] = {
                            'uuid': output[0]['result']['start_concept']['uuid'],
                            'related_chunks': output[0]['result']['related_chunks'],
                            'related_concepts': output[0]['result']['related_concepts']
                        }
            else:
                similar_topic = GraphQueryService.get_most_similar_topic(topic_name=query_str, similarity_threshold=0.7)
                
                if not similar_topic:
                    return None

                output = GraphQueryService.get_topic_graph_for_topic_uuid(
                    topic_uuid=similar_topic['uuid'], 
                    num_chunks=3,
                    num_related_concepts=25,
                    param=param,
                    id=id
                    )

                if not output:
                    return None

                context_nodes[similar_topic['id']] = output[0]['result']

            logging.info(f"Context nodes: {context_node['id']}" for context_node in context_nodes)
            
            return context_nodes
        except Exception as e:
            logging.error(f"Error getting context: {e}")
            return None