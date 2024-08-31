from enum import Enum
import logging
from typing import Dict, List
from flask_app.services.EntityExtractionService import EntityExtractor
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
    

class QuestionModel(BaseModel):
    question_type: QuestionType = Field(
        description="The type of question the user is asking."
    )

class ContextService():
    @staticmethod
    def get_context(question_type, query_str):
        entities = EntityExtractor.get_similies(query_str=query_str)

        if question_type == QuestionType.EXPLORE:
            return ContextService.get_explore_context(query_str)
        elif question_type == QuestionType.ANSWER:
            return ContextService.get_answer_context(query_str)
        elif question_type == QuestionType.RELATIONSHIP:
            return ContextService.get_relationship_context(query_str)
        elif question_type == QuestionType.FOLLOWUP:
            return ContextService.get_followup_context(query_str)
        else:
            return None
        
    @staticmethod
    def get_explore_context(query_str):
        return None
    
    @staticmethod
    def get_answer_context(query_str):
        return None
    
    @staticmethod
    def get_relationship_context(query_str):
        return None
    
    @staticmethod
    def get_followup_context(query_str):
        return None
    
    @staticmethod
    def get_context_nodes(query_str: str, entities) -> Dict[str, str]:
        context_nodes = {}

        if entities:
            for entity in entities:
                similar_topic = GraphQueryService.get_most_similar_topic(topic_name=entity)
                output = GraphQueryService.get_topic_graph_for_topic_uuid(topic_uuid=similar_topic['uuid'], num_chunks=3)

                if not output:
                    return None

                context_nodes[similar_topic['id']] = {
                    'uuid': output[0]['result']['start_concept']['uuid'],
                    'related_chunks': output[0]['result']['related_chunks'],
                    'related_concepts': output[0]['result']['related_concepts']
                }
        else:
            similar_topic = GraphQueryService.get_most_similar_topic(topic_name=query_str)
            output = GraphQueryService.get_topic_graph_for_topic_uuid(topic_uuid=similar_topic['uuid'], num_chunks=3)

            if not output:
                return None

            context_nodes[similar_topic['id']] = output[0]['result']
        
        return context_nodes