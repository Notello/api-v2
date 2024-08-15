from typing import List

from langchain_core.pydantic_v1 import BaseModel, Field

class Node(BaseModel):
    id: str = Field(description="Name or human-readable unique identifier.")

class Relationship(BaseModel):
    source: Node = Field(description="Name or human-readable unique identifier of source node, must match a node in the nodes list")
    target: Node = Field(description="Name or human-readable unique identifier of target node, must match a node in the nodes list")
    type: str = Field(description="The type of the relationship.")

class KnowledgeGraph(BaseModel):
    nodes: List[Node] = Field(description="List of concept or entity nodes")
    relationships: List[Relationship] = Field(description="List of relationships between concepts or entities")