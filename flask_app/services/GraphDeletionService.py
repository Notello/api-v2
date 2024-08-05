import logging
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.shared.common_fn import get_graph

class GraphDeletionService():
    @staticmethod
    def delete_node_for_param(param, id):
        if param not in ['courseId', 'noteId']:
            raise ValueError("param must be either 'courseId' or 'noteId'")
        
        logging.info(f"Deleting nodes with {param} = {id}")

        graphAccess = graphDBdataAccess(get_graph())

        query = f"""
        MATCH (n)
        WHERE $id IN n.{param}
        WITH n, [x IN n.{param} WHERE x <> $id] AS remaining_{param}
        SET n.{param} = remaining_{param}
        WITH n, remaining_{param}
        WHERE size(remaining_{param}) = 0
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """
       
        params = {
            'id': id
        }

        result = graphAccess.execute_query(query, params)

        logging.info(f"Deleted {result} nodes")