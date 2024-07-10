import logging
from flask_restx import Namespace, Resource
from flask import request


from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.HelperService import HelperService

api = Namespace('graph')

@api.route('/get-graph-for/<string:param>/<string:id>')
class GetGraphFor(Resource):
    def get(self, param, id):
        try:
            logging.info(f"Get graph for {param}, {id}")

            if not HelperService.validate_all_uuid4(id):
                return {f'message': 'Invalid {param} id'}, 400
            
            nodes, relationships = GraphQueryService.get_graph_for_param(key=param, value=id)

            if nodes is None or relationships is None:
                return {'message': 'Error getting graph'}, 400

            logging.info(f"Graph, nodes: {len(nodes)}, relationships: {len(relationships)}")

            return {
                'nodes': nodes,
                'relationships': relationships
                }, 200
        except Exception as e:
            message = f" Unable to get notes for {param} {id}, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400