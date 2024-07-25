from flask_restx import Namespace, Resource

from flask_app.services.NodeUpdateService import NodeUpdateService
from flask_app.services.GraphQueryService import GraphQueryService

api = Namespace('test')

@api.route('/pagerank/<string:topic>')
class PageRank(Resource):
    def get(self, topic):
        return GraphQueryService.get_topic_graph_for_topic_uuid(topic_uuid=topic)
        