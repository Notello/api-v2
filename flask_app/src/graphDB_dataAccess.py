import logging
from typing import Any
from flask_app.src.entities.source_node import sourceNode
from flask_app.constants import NOTEID
from flask_app.services.Neo4jConnection import Neo4jConnection

from dotenv import load_dotenv
load_dotenv()

class graphDBdataAccess:
    def create_source_node(self, obj_source_node: sourceNode):
        logging.info(f'Creating source node if it does not exist obj_source_node: {obj_source_node}')
        try:
            attributes = {attr: getattr(obj_source_node, attr) for attr in vars(obj_source_node) if getattr(obj_source_node, attr) is not None}
            attributes['status'] = "New"

            query = """
            MERGE (d:Document {noteId: $noteId})
            SET d += $attributes
            """

            params = {
                "noteId": obj_source_node.noteId,
                "attributes": attributes
            }

            Neo4jConnection.run_query(query, params)

            logging.info("Source node created successfully")
        except Exception as e:
            error_message = str(e)
            logging.exception(f"Error creating source node: {error_message}")
            raise Exception(error_message)

    def update_source_node(self, obj_source_node: sourceNode):
        try:
            attributes = {attr: getattr(obj_source_node, attr) for attr in vars(obj_source_node) if getattr(obj_source_node, attr) is not None}

            if NOTEID not in attributes or not attributes[NOTEID]:
                raise ValueError("noteId must be provided and cannot be empty.")

            query = """
            MERGE (d:Document {noteId: $noteId})
            SET d += $attributes
            """

            params = {
                "noteId": attributes[NOTEID],
                "attributes": attributes
            }

            logging.info("Updating source node properties")
            
            Neo4jConnection.run_query(query, params)

        except Exception as e:
            error_message = str(e)
            logging.exception(f"Error updating source node: {error_message}")
            raise Exception(error_message)

    def connection_check(self):
        try:
            Neo4jConnection.run_query("RETURN 1")
            return "Connection Successful"
        except Exception as e:
            logging.exception("Connection check failed")
            return f"Connection Failed: {str(e)}"

    def execute_query(self, query: str, params: dict[str, Any] = None):
        try:
            return Neo4jConnection.run_query(query, params)
        except Exception as e:
            logging.exception(f"Query execution failed: {query}")
            raise Exception(f"Query execution failed: {str(e)}")