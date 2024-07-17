from flask_restx import Namespace, Resource

from flask_app.services.NodeUpdateService import NodeUpdateService
from flask_app.services.GraphQueryService import GraphQueryService

api = Namespace('test')

@api.route('/pagerank/<string:param>/<string:id>')
class PageRank(Resource):
    def get(self, param, id):
        return GraphQueryService.get_importance_graph_by_param(param=param, id=id)
        