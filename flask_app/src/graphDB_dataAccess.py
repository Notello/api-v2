import logging
import os
from flask import current_app
from langchain_community.graphs import Neo4jGraph
from flask_app.src.shared.common_fn import delete_uploaded_local_file
from flask_app.src.entities.source_node import sourceNode
import json

class graphDBdataAccess:

    def __init__(self, graph: Neo4jGraph):
        self.graph = graph

    def update_exception_db(self, file_name, exp_msg):
        try:
            job_status = "Failed"
            result = self.get_current_status_document_node(file_name)
            print(f'result : {result}')
            is_cancelled_status = result[0]['is_cancelled']
            if is_cancelled_status == 'True':
                job_status = 'Cancelled'
            self.graph.query("""MERGE(d:Document {fileName :$fName}) SET d.status = $status, d.errorMessage = $error_msg""",
                            {"fName":file_name, "status":job_status, "error_msg":exp_msg})
        except Exception as e:
            error_message = str(e)
            logging.error(f"Error in updating document node status as failed: {error_message}")
            raise Exception(error_message)
        
    def create_source_node(self, obj_source_node: sourceNode):
        logging.info(f'creating source node if it does not exist obj_source_node : {obj_source_node}')
        for key in obj_source_node.__dict__:
            logging.info(f'key : {key}, value : {obj_source_node.__dict__[key]}')
        try:
            job_status = "New"

            attributes = {attr: getattr(obj_source_node, attr) for attr in vars(obj_source_node) if getattr(obj_source_node, attr) is not None}

            attributes['status'] = job_status

            merge_clause = "MERGE (d:Document {fileName: $fileName})"

            set_clause = "SET " + ", ".join([f"d.{k} = ${k}" for k in attributes.keys()])

            query = f"""
                {merge_clause}
                {set_clause}
            """

            logging.info(f'query : {query}')

            graph: Neo4jGraph = current_app.config["NEO4J_GRAPH"]

            graph.query(query, attributes)

            logging.info(f"source node created successfully")

        except Exception as e:
            error_message = str(e)
            logging.exception(f"error_message = {error_message}")
            raise Exception(error_message)

        
    def update_source_node(self, obj_source_node: sourceNode):
        try:
            attributes = {attr: getattr(obj_source_node, attr) for attr in vars(obj_source_node) if getattr(obj_source_node, attr) is not None}

            if 'fileName' not in attributes or not attributes['fileName']:
                raise ValueError("fileName must be provided and cannot be empty.")

            params = {"props": attributes}

            query = "MERGE (d:Document {fileName: $props.fileName}) SET d += $props"

            logging.info("Updating source node properties")

            graph: Neo4jGraph = current_app.config["NEO4J_GRAPH"]

            graph.query(query, params)
        except Exception as e:
            error_message = str(e)
            logging.info(f"error_message = {error_message}")
            raise Exception(error_message)
    
    def get_source_list(self):
        """
        Args:
            uri: URI of the graph to extract
            db_name: db_name is database name to connect to graph db
            userName: Username to use for graph creation ( if None will use username from config file )
            password: Password to use for graph creation ( if None will use password from config file )
            file: File object containing the PDF file to be used
            model: Type of model to use ('Diffbot'or'OpenAI GPT')
        Returns:
        Returns a list of sources that are in the database by querying the graph and
        sorting the list by the last updated date. 
        """
        logging.info("Get existing files list from graph")
        query = "MATCH(d:Document) WHERE d.fileName IS NOT NULL RETURN d ORDER BY d.updatedAt DESC"
        result = self.graph.query(query)
        list_of_json_objects = [entry['d'] for entry in result]
        return list_of_json_objects
        
    def update_KNN_graph(self):
        """
        Update the graph node with SIMILAR relationship where embedding scrore match
        """
        index = self.graph.query("""show indexes yield * where type = 'VECTOR' and name = 'vector'""")
        # logging.info(f'show index vector: {index}')
        knn_min_score = os.environ.get('KNN_MIN_SCORE', 0.6)
        if index[0]['name'] == 'vector':
            logging.info('update KNN graph')
            result = self.graph.query("""MATCH (c:Chunk)
                                    WHERE c.embedding IS NOT NULL AND count { (c)-[:SIMILAR]-() } < 5
                                    CALL db.index.vector.queryNodes('vector', 6, c.embedding) yield node, score
                                    WHERE node <> c and score >= $score MERGE (c)-[rel:SIMILAR]-(node) SET rel.score = score
                                """,
                                {"score":float(knn_min_score)}
                                )
            logging.info(f"result : {result}")
            
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

    def get_current_status_document_node(self, file_name):
        query = """
                MATCH(d:Document {fileName : $file_name}) RETURN d.status AS Status , d.processingTime AS processingTime, 
                d.nodeCount AS nodeCount, d.model as model, d.relationshipCount as relationshipCount,
                d.total_pages AS total_pages, d.total_chunks AS total_chunks , d.fileSize as fileSize, 
                d.is_cancelled as is_cancelled, d.processed_chunk as processed_chunk
                """
        param = {"file_name" : file_name}
        return self.execute_query(query, param)
    
    def delete_file_from_graph(self, filenames, source_types, deleteEntities:str, merged_dir:str):
        # filename_list = filenames.split(',')
        filename_list= list(map(str.strip, json.loads(filenames)))
        source_types_list= list(map(str.strip, json.loads(source_types)))
        # source_types_list = source_types.split(',')
        for (file_name,source_type) in zip(filename_list, source_types_list):
            merged_file_path = os.path.join(merged_dir, file_name)
            if source_type == 'local file':
                logging.info(f'Deleted File Path: {merged_file_path} and Deleted File Name : {file_name}')
                delete_uploaded_local_file(merged_file_path, file_name)

        query_to_delete_document=""" 
           MATCH (d:Document) where d.fileName in $filename_list and d.fileSource in $source_types_list
            with collect(d) as documents 
            unwind documents as d
            optional match (d)<-[:PART_OF]-(c:Chunk) 
            detach delete c, d
            return count(*) as deletedChunks
            """
        query_to_delete_document_and_entities=""" 
            MATCH (d:Document) where d.fileName in $filename_list and d.fileSource in $source_types_list
            with collect(d) as documents 
            unwind documents as d
            optional match (d)<-[:PART_OF]-(c:Chunk)
            // if delete-entities checkbox is set
            call { with  c, documents
                match (c)-[:HAS_ENTITY]->(e)
                // belongs to another document
                where not exists {  (d2)<-[:PART_OF]-()-[:HAS_ENTITY]->(e) WHERE NOT d2 IN documents }
                detach delete e
                return count(*) as entities
            } 
            detach delete c, d
            return sum(entities) as deletedEntities, count(*) as deletedChunks
            """    
        param = {"filename_list" : filename_list, "source_types_list": source_types_list}
        if deleteEntities == "true":
            result = self.execute_query(query_to_delete_document_and_entities, param)
            logging.info(f"Deleting {len(filename_list)} documents = '{filename_list}' from '{source_types_list}' from database")
        else :
            result = self.execute_query(query_to_delete_document, param)    
            logging.info(f"Deleting {len(filename_list)} documents = '{filename_list}' from '{source_types_list}' with their entities from database")
        
        return result, len(filename_list)    