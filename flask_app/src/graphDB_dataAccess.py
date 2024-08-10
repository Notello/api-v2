import logging
import os
from langchain_community.graphs import Neo4jGraph
from flask_app.src.entities.source_node import sourceNode
import json
from flask_app.constants import NOTEID
from flask_app.src.shared.common_fn import get_graph

from dotenv import load_dotenv
load_dotenv()

class graphDBdataAccess:

    def __init__(self):
        self.graph = get_graph()
        
    def create_source_node(self, obj_source_node: sourceNode):
        logging.info(f'creating source node if it does not exist obj_source_node : {obj_source_node}')
        for key in obj_source_node.__dict__:
            logging.info(f'key : {key}, value : {obj_source_node.__dict__[key]}')
        try:
            attributes = {attr: getattr(obj_source_node, attr) for attr in vars(obj_source_node) if getattr(obj_source_node, attr) is not None}

            attributes['status'] = "New"

            merge_clause = "MERGE (d:Document {noteId: $noteId})"

            set_clause = "SET " + ", ".join([f"d.{k} = ${k}" for k in attributes.keys()])

            query = f"""
                {merge_clause}
                {set_clause}
            """

            logging.info(f'query : {query}')

            self.graph.query(query, attributes)

            logging.info(f"source node created successfully")

        except Exception as e:
            error_message = str(e)
            logging.exception(f"error_message = {error_message}")
            raise Exception(error_message)

        
    def update_source_node(self, obj_source_node: sourceNode):
        try:
            attributes = {attr: getattr(obj_source_node, attr) for attr in vars(obj_source_node) if getattr(obj_source_node, attr) is not None}

            if 'noteId' not in attributes or not attributes[NOTEID]:
                raise ValueError("noteId must be provided and cannot be empty.")

            params = {"props": attributes}

            query = "MERGE (d:Document {noteId: $props.noteId}) SET d += $props"

            logging.info("Updating source node properties")

            self.graph.query(query, params)
        except Exception as e:
            error_message = str(e)
            logging.info(f"error_message = {error_message}")
            raise Exception(error_message)
            
    def connection_check(self):
        """
        Args:
            uri: URI of the graph to extract
            userName: Username to use for graph creation ( if None will use username from config file )
            password: Password to use for graph creation ( if None will use password from config file )
            db_name: db_name is database name to connect to graph db
        Returns:
        Returns a status of connection from NEO4j is success or failure
        """
        if self.graph:
            return "Connection Successful"

    def execute_query(self, query, param=None):
        return self.graph.query(query, param)