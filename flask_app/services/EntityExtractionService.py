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

def setup_llm(
    text: str,
):
    prompt_template_entities = f"""
    Extract all named entities or proper nouns such as names of people, organizations, concepts, ideas or locations
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
    def get_context_nodes(query_str: str) -> Dict[str, str]:
        entites = EntityExtractor.extract_entities(query_str=query_str)

        context_nodes = {}

        if entites:
            for entity in entites:
                similar_topic = GraphQueryService.get_most_similar_topic(topic_name=entity)
                output = GraphQueryService.get_topic_graph_for_topic_uuid(topic_uuid=similar_topic['uuid'], num_chunks=3)

                if not output:
                    return None

                context_nodes[similar_topic['id']] = output[0]['result']
        else:
            similar_topic = GraphQueryService.get_most_similar_topic(topic_name=query_str)
            output = GraphQueryService.get_topic_graph_for_topic_uuid(topic_uuid=similar_topic['uuid'], num_chunks=3)

            if not output:
                return None

            context_nodes[similar_topic['id']] = output[0]['result']
        
        return context_nodes