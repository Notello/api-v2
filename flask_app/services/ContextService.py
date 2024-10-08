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
from flask_app.services.SupaGraphService import SupaGraphService

class QuestionType(str, Enum):
    META_GENERAL = "meta_general"
    FACT_BASED = "fact_based"
    PROBLEM_SOLVING = "problem_solving"
    EXPLORE = "explore"
    STUDY_CREATION = "study_creation"
    STUDY_QUESTION = "study_question"

class QuestionModel(BaseModel):
    question_type: QuestionType = Field(
        description="The type of question the user is asking."
    )


class ContextService():
    @staticmethod
    def get_context_nodes(question_type, query_str, history, param, id, courseId):
        logging.info(f"question_type: {question_type}")
        if question_type == QuestionType.META_GENERAL:
            return SupaGraphService.get_meta_context(
                param=param,
                id=id,
                courseId=courseId
            )
        elif question_type == QuestionType.FACT_BASED:
            return SupaGraphService.get_context(
                param=param,
                id=id,
                query_str=query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history),
                num_chunks=15,
                num_related_concepts=10,
                courseId=courseId
            )
        elif question_type == QuestionType.PROBLEM_SOLVING:
            return SupaGraphService.get_context(
                param=param,
                id=id,
                query_str=query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history),
                num_chunks=10,
                num_related_concepts=10,
                courseId=courseId
            )
        elif question_type == QuestionType.EXPLORE:
            return SupaGraphService.get_context(
                param=param,
                id=id,
                query_str=query_str, 
                entities=EntityExtractor.get_similies(query_str=query_str, history=history),
                num_chunks=15,
                num_related_concepts=50,
                courseId=courseId
            )
        else:
            return None