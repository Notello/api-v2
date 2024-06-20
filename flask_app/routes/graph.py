import logging
from flask_restx import Namespace, Resource


from flask_app.services.GraphService import GraphService
from flask_app.services.HelperService import HelperService

api = Namespace('graph')

@api.route('/get-graph-for/<string:param>/<string:id>')
class GetGraphForCourse(Resource):
    def get(self, param, id):
        try:
            logging.info(f"Get graph for {param}, {id}")

            if not HelperService.validate_uuid4(id):
                return {f'message': 'Invalid {param} id'}, 400
            
            nodes, relationships = GraphService.get_graph_for_param(key=param, value=id)

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