import logging
from flask_restx import Namespace, Resource
from datetime import datetime


from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.HelperService import HelperService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.constants import COURSEID
from flask_app.routes.middleware import token_required

api = Namespace('graph')

@api.route('/get-graph-for/<string:param>/<string:id>')
class GetGraphFor(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, param, id):
        try:
            logging.info(f"Get graph for {param}, {id}")

            if not HelperService.validate_all_uuid4(id) or \
                not SupabaseService.param_id_exists(param, id):
                logging.info(f"Invalid {param} id: {id}")
                return {f'message': 'Invalid {param} id'}, 400
            
            start = datetime.now()
            logging.info(f"starting at {datetime.now()}")
            nodes, relationships = GraphQueryService.get_graph_for_param(key=param, value=id)

            logging.info(f"ending at {datetime.now()}")
            logging.info(f"query took: {datetime.now() - start}")

            if nodes is None or relationships is None:
                logging.error(f"Error getting graph for {param} {id}")
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
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self, topicId):
        try:
            args = topic_graph_parser.parse_args()
            courseId = args.get(COURSEID, None)
            logging.info(f"Get topic graph for {topicId}")
            
            if not HelperService.validate_all_uuid4(topicId, courseId) \
                or not SupabaseService.param_id_exists('courseId', courseId):
                logging.info(f"Invalid topic or course uuid: {topicId}, {courseId}")
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
        
@api.route('/get-topic-list-for-param/<string:param>/<string:id>')
class GetTopicListForParam(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, param, id):
        try:
            logging.info(f"Get topic list for {param}, {id}")

            if not HelperService.validate_all_uuid4(id) or \
                not SupabaseService.param_id_exists(param, id):
                logging.info(f"Invalid {param} id: {id}")
                return {f'message': 'Invalid {param} id'}, 400

            topics = GraphQueryService.get_topics_for_param(param=param, id=id)

            if topics is None:
                return {'message': 'Error getting graph'}, 400
        
            return topics, 200
        except Exception as e:
            message = f" Unable to get notes for {param} {id}, Exception: {e}"
            logging.exception(f" Unable to get notes for {param} {id}, Exception: {e}")
            return {'message': message}, 400

@api.route('/get-num-topics-for-param/<string:param>/<string:id>')
class GetTopicListForParam(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, param, id):
        try:
            logging.info(f"Get topic list for {param}, {id}")

            if not HelperService.validate_all_uuid4(id) or \
                not SupabaseService.param_id_exists(param, id):
                logging.info(f"Invalid {param} id: {id}")
                return {f'message': 'Invalid {param} id'}, 400

            num_topics = GraphQueryService.get_num_topics_for_param(param=param, id=id)

            if num_topics is None:
                return {'message': 'Error getting graph'}, 400
        
            return num_topics, 200
        except Exception as e:
            message = f" Unable to get notes for {param} {id}, Exception: {e}"
            logging.exception(f" Unable to get notes for {param} {id}, Exception: {e}")
            return {'message': message}, 400
        
@api.route('/get-notes-for-topic/<string:topicId>')
class GetNotesForTopic(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, topicId):
        try:
            logging.info(f"Get notes for topicId: {topicId}")

            if not HelperService.validate_all_uuid4(topicId):
                logging.info(f"Invalid topicId: {topicId}")
                return {f'message': 'Invalid topicId'}, 400

            notes = GraphQueryService.get_notes_for_topic(uuid=topicId)

            if notes is None:
                return {'message': 'Error getting notes'}, 400

            return notes, 200
        except Exception as e:
            logging.exception(f"Unable to get notes for topicId {topicId}, Exception: {e}")
            return {'message': f"Unable to get notes for topicId {topicId}, Exception: {e}"}, 400