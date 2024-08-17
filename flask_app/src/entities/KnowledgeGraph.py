import json
import logging
from typing import List, Dict, Any
from langchain_core.pydantic_v1 import BaseModel, Field, validator

class Node(BaseModel):
    id: str = Field(description="Name or human-readable unique identifier.")

class Relationship(BaseModel):
    source: str = Field(description="Name or human-readable unique identifier of source node, must match a node in the nodes list")
    target: str = Field(description="Name or human-readable unique identifier of target node, must match a node in the nodes list")
    type: str = Field(description="The type of the relationship.")

class KnowledgeGraph(BaseModel):
    nodes: List[Node] = Field(description="List of concept or entity nodes")
    relationships: List[Relationship] = Field(description="List of relationships between concepts or entities")

    @staticmethod
    def parse_llm_output(output) -> Dict[str, Any]:
        if not output["parsed"]:
            argument_json = json.loads(
                    output["raw"].additional_kwargs["tool_calls"][0]["function"][
                        "arguments"
                    ]
                )
            
            logging.info(f"Argument JSON: {argument_json}")

            knowledge_graph = KnowledgeGraph(nodes=[], relationships=[])

            for node in argument_json["nodes"]:
                if not node.get("id"):  # Id is mandatory, skip this node
                    continue
                knowledge_graph.nodes.append(Node(
                    id=node["id"]
                ))

            for relationship in argument_json["relationships"]:
                if not relationship.get("source_node_id") or not relationship.get("target_node_id") or not relationship.get("type"):
                    continue
                knowledge_graph.relationships.append(Relationship(
                    source=relationship["source_node_id"],
                    target=relationship["target_node_id"],
                    type=relationship["type"]
                ))

            return knowledge_graph
        else:
            logging.info("No errors found in LLM output")
            return output["parsed"]