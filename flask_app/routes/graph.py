import logging
from flask_restx import Namespace, Resource


from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.HelperService import HelperService
from flask_app.constants import COURSEID

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
        
topic_graph_parser = api.parser()

topic_graph_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the quiz')
@api.expect(topic_graph_parser)
@api.route('/get-topic-graph-for-topic/<string:topicId>')
class GetGraphFor(Resource):
    def post(self, topicId):
        try:
            args = topic_graph_parser.parse_args()
            courseId = args.get(COURSEID, None)
            logging.info(f"Get topic graph for {topicId}")
            
            if not HelperService.validate_all_uuid4(topicId, courseId):
                return {f'message': 'Invalid topic or course uuid'}, 400
            
            nodes, relationships = GraphQueryService.get_display_topic_graph(uuid=topicId, courseId=courseId)
            
            return {
                'nodes': nodes,
                'relationships': relationships
                }, 200
        
        except Exception as e:
            message = f" Unable to get topic graph for {topicId}, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400