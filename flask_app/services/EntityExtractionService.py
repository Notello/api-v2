import logging
from typing import Any, Dict, Optional

from langchain_core.pydantic_v1 import BaseModel, Field
from typing import Optional, List
from langchain_core.prompts import ChatPromptTemplate

from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import GPT_4O_MINI

class Entities(BaseModel):
    entities: Optional[List[str]] = Field(
        description="A list of the named entites in the text relevant to the current question considering the entire conversation history."
    )

class SynonymList(BaseModel):
    entity: str = Field(description="The original entity")
    synonyms: List[str] = Field(description="A list of synonyms for the entity")

class SimilarTopics(BaseModel):
    all_synonyms: List[SynonymList] = Field(description="A list of synonym lists for each entity")


def setup_llm(
    text: str,
    history_str: str
):
    prompt_template_entities = f"""
    You are an expert at extracting relevant entities for context-aware question answering. 
    Your task is to identify the most important entities needed to answer the given question, considering the provided conversation history.

    Guidelines:
    1. Focus on entities directly relevant to answering the current question.
    2. Include entities from the history only if they are necessary for understanding or answering the current question.
    3. Prioritize entities mentioned in the most recent parts of the conversation.
    4. Include both explicitly mentioned entities and those referred to by pronouns if their antecedents are clear.
    5. Exclude general concepts or ideas unless they are crucial to the question.
    6. Aim for precision: include only the most relevant entities, typically 2-4 per question.

    History:
    {history_str}

    Current Question:
    {text}
    """

    extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(Entities)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_template_entities),
    ])
    
    logging.info(text)
    return extraction_prompt | extraction_llm


class EntityExtractor():
    @staticmethod
    def extract_entities(query_str: str, history: List[str]) -> str:
        history_str = ""
        if history:
            history_str = "\n".join(history)

        extraction_chain = setup_llm(
            text=query_str,
            history_str=history_str
        )

        result = extraction_chain.invoke({})

        logging.info(f"Entities: {result.entities}")

        return result.entities
    
    @staticmethod
    def escape_template_variables(s):
        return s.replace("{", "{{").replace("}", "}}")
    
    @staticmethod
    def get_similies(query_str: str, history: List[str]):
        query_str = EntityExtractor.escape_template_variables(query_str)

        entities = EntityExtractor.extract_entities(query_str=query_str, history=history)

        return entities
    
    @staticmethod
    def get_similar_topics(entities: List[str]) -> List[Dict[str, List[str]]]:
        logging.info(f"Entities: {entities}")

        llm = get_llm(GPT_4O_MINI).with_structured_output(SimilarTopics)
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
             You are a synonym generator. 
             Given a list of entities, return a list of synonym lists, where each item contains the original entity and a list of 10 synonyms, related terms, or closely associated concepts for that entity.
             Focus on providing accurate, relevant, and closely related terms.
             For technical or specific terms, include abbreviations, alternative names, and closely related concepts.
             Do not include the original entity in the list of synonyms.
             """),
            ("user", f"Entities: {entities}")
        ])

        invokable = prompt | llm

        result: SimilarTopics = invokable.invoke({})

        logging.info(f"Result: {result}")

        return result