from langchain_core.pydantic_v1 import BaseModel, Field
from typing import Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from retry import retry

class EntityGroup(BaseModel):
    final_label: str = Field(description="The final label for the merged entity")
    entities: List[str] = Field(description="List of entities to be merged into the final label")

class Disambiguate(BaseModel):
    merge_groups: List[EntityGroup] = Field(
        description="Groups of entities that should be merged, with their final labels"
    )

def setup_llm():
    system_prompt = """You are a data processing assistant. Your task is to identify duplicate entities in a list and decide which of them should be merged.
    The entities might be slightly different in format or content, but essentially refer to the same thing. Use your analytical skills to determine duplicates.

    Here are the rules for identifying duplicates:
    1. You do not need to merge all entities, it is up to your discretion.
    2. Entities with minor typographical differences should be considered duplicates.
    3. Entities with different formats but the same content should be considered duplicates.
    4. Entities should only be merged if they refer to the same real-world object or concept.
    5. If it refers to different numbers, dates, or products, do not merge results.
    6. If it refers to a name of a person or thing, choose the full name as the final label.

    ## IMPORTANT NOTES:
    - Do not merge nodes just because they have the same words in them, they MUST be the same real world entity.
    - Example: entity1 = 'America', entity2 = 'American Football', DO NOT merge these entities (One is a country, the other is a sport).
    - Example: entity1 = 'New York', entity2 = 'New York City', DO merge these entities (they are the same city).
    - Example: entity1 = 'Aidan Gollan', entity2 = 'Audrey Gollan', DO merge these entities (they are siblings not the same person).

    Your output should be a list of groups, where each group is represented by a dictionary. The dictionary should have a 'final_label' key with the chosen label for the merged entity, and an 'entities' key with a list of all entities that should be merged into this label.
    """
    
    user_template = """
    Here is the list of entities to process:
    {entities}

    Please identify duplicates, merge them, and provide the merged groups in the specified format.
    """

    extraction_llm = ChatOpenAI(model_name='gpt-3.5-turbo-0125').with_structured_output(Disambiguate)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

@retry(tries=3, delay=2)
def entity_resolution(entities: List[str]) -> Optional[List[Dict[str, List[str]]]]:
    extraction_chain = setup_llm()
    result = extraction_chain.invoke({"entities": entities})
    
    return [
        {group.final_label: group.entities}
        for group in result.merge_groups
    ]