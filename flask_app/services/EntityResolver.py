from langchain_core.pydantic_v1 import BaseModel, Field
from typing import Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import GPT_4O_MINI
from retry import retry

class EntityGroup(BaseModel):
    final_label: str = Field(description="The final label for the merged entity")
    entities: List[str] = Field(description="List of entities to be merged into the final label")

class Disambiguate(BaseModel):
    merge_groups: List[EntityGroup] = Field(
        description="Groups of entities that should be merged, with their final labels"
    )

def setup_llm():
    system_prompt = """You are a data processing assistant tasked with identifying and merging entities in a list that refer to the same real-world concept, while keeping different versions or types separate. Your goal is to merge entities that are essentially the same, even if they have slight variations in wording, but maintain distinctions between different versions or types of entities.

    Guidelines for identifying and merging entities:
    1. Merge entities that refer to the same real-world concept, even if they have slight variations in wording or formatting.
    2. Consider context and common sense when deciding whether to merge entities.
    3. Merge variations of the same person's name (e.g., "John Smith" and "J. Smith").
    4. Merge entities with minor differences in articles or prepositions (e.g., "apple" and "the apple", "computer" and "a computer").
    5. Keep different versions, models, or types of the same general category separate (e.g., "iPhone 12" and "iPhone 13" should not be merged).
    6. Do not merge entities that represent different levels of specificity or hierarchy (e.g., "New York City" and "New York State" should remain separate).
    7. When in doubt about whether merging would lose important distinctions, err on the side of keeping entities separate.

    Examples of appropriate merging:
    - "apple" and "the apple" -> merge
    - "J. Smith" and "John Smith" -> merge
    - "Computer" and "A computer" -> merge
    - "USA", "United States", "United States of America" -> merge
    - "COVID-19", "Coronavirus", "SARS-CoV-2" -> merge

    Examples where entities should remain separate:
    - "iPhone 12" and "iPhone 13" -> keep separate
    - "acid" and "nucleic acid" -> keep separate
    - "New York City" and "New York State" -> keep separate
    - "Python 3.8" and "Python 3.9" -> keep separate

    Your output should be a list of groups, where each group is represented by a dictionary. The dictionary should have a 'final_label' key with the chosen label for the merged entity, and an 'entities' key with a list of all entities that should be merged into this label.
    """
    
    user_template = """
    Here is the list of entities to process:
    {entities}

    Please identify and merge entities that refer to the same real-world concept, even if they have slight variations in wording. However, keep different versions or types separate. Provide the merged groups in the specified format.
    """

    extraction_llm = get_llm(model_name=GPT_4O_MINI).with_structured_output(Disambiguate)
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