import logging
from typing import Any, Dict, Optional

from langchain_core.pydantic_v1 import BaseModel, Field
from typing import Optional, List
from langchain_core.prompts import ChatPromptTemplate

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import GPT_4O_MINI

class Entities(BaseModel):
    entities: Optional[List[str]] = Field(
        description="A list of the named entites in the text."
    )

class SynonymList(BaseModel):
    entity: str = Field(description="The original entity")
    synonyms: List[str] = Field(description="A list of synonyms for the entity")

class SimilarTopics(BaseModel):
    all_synonyms: List[SynonymList] = Field(description="A list of synonym lists for each entity")


def setup_llm(
    text: str,
):
    prompt_template_entities = f"""
    Extract nouns or entities from the following text
    from the following text:
    {text}
    """

    extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(Entities)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_template_entities),
    ])
    
    return extraction_prompt | extraction_llm


class EntityExtractor():
    @staticmethod
    def extract_entities(query_str: str) -> str:
        extraction_chain = setup_llm(
            text=query_str
        )

        result = extraction_chain.invoke({})

        return result.entities
    
    @staticmethod
    def get_similies(query_str: str) -> List[Dict[str, str]]:
        entites = EntityExtractor.extract_entities(query_str=query_str)

        similies = EntityExtractor.get_similar_topics(entities=entites)

        return similies
    
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

        return [{"entity": synonym_list.entity, "synonyms": synonym_list.synonyms} for synonym_list in result.all_synonyms]