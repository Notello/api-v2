from typing import List, Optional
from langchain_core.pydantic_v1 import BaseModel, Field, validator

class Node(BaseModel):
    id: str = Field(description="Name or human-readable unique identifier.")

    @validator('id')
    def id_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('id must not be empty')
        return v

class Relationship(BaseModel):
    source: str = Field(description="Name or human-readable unique identifier of source node, must match a node in the nodes list")
    target: str = Field(description="Name or human-readable unique identifier of target node, must match a node in the nodes list")
    type: str = Field(description="The type of the relationship.")

    @validator('source', 'target', 'type')
    def fields_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('field must not be empty')
        return v

class KnowledgeGraph(BaseModel):
    nodes: List[Node] = Field(description="List of concept or entity nodes")
    relationships: List[Relationship] = Field(description="List of relationships between concepts or entities")

    @validator('nodes', 'relationships', pre=True, each_item=True)
    def validate_items(cls, v):
        try:
            if isinstance(v, dict):
                return Node(**v) if 'id' in v else Relationship(**v)
            return v
        except ValueError:
            return None

    @validator('nodes', 'relationships')
    def filter_none_values(cls, v):
        return [item for item in v if item is not None]