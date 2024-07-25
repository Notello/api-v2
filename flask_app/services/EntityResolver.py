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
    system_prompt = """You are a data processing assistant tasked with identifying and merging duplicate entities in a list. Your primary focus is on preserving important details while still combining entities that reasonably refer to the same concept, object, person, or place.

    Guidelines for identifying and merging entities:
    1. Merge entities that refer to the same real-world concept, even if they have slight variations in wording or formatting.
    2. Preserve important distinctions and details. If merging would result in a loss of significant information, keep the entities separate.
    3. Consider context and common sense when deciding whether to merge entities.
    4. For people's names, merge variations of the same person's name (e.g., "John Smith" and "J. Smith") but keep distinct individuals separate.
    5. For place names, merge entities that refer to the same location, but be mindful of different levels of specificity (e.g., keep "New York City" and "New York State" separate).
    6. For product names or brands, merge clear variations of the same product but keep distinct products or models separate.
    7. Merge numbers or measurements only if they represent the same quantity in different formats.
    8. When in doubt about whether merging would lose important detail, err on the side of keeping entities separate.

    Examples of appropriate merging:
    - "USA", "United States", "United States of America" -> merge
    - "Einstein", "Albert Einstein", "A. Einstein" -> merge
    - "COVID-19", "Coronavirus", "SARS-CoV-2" -> merge
    - "100 km", "100 kilometers" -> merge

    Examples where entities should remain separate:
    - "Apple (company)" and "Apple (fruit)" -> keep separate
    - "Python (programming)" and "python (snake)" -> keep separate
    - "50 km" and "50 miles" -> keep separate
    - "New York City" and "New York State" -> keep separate

    Your output should be a list of groups, where each group is represented by a dictionary. The dictionary should have a 'final_label' key with the chosen label for the merged entity, and an 'entities' key with a list of all entities that should be merged into this label.
    """
    
    user_template = """
    Here is the list of entities to process:
    {entities}

    Please identify and merge duplicate entities, focusing on preserving important details while still combining entities that reasonably refer to the same concept. Provide the merged groups in the specified format.
    """

    extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(Disambiguate)
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