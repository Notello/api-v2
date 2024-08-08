import logging
from flask_restx import Namespace, Resource
from flask import g

from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.SummaryService import SummaryService
from flask_app.services.AuthService import AuthService
from flask_app.services.RatelimitService import RatelimitService
from flask_app.routes.middleware import token_required
from flask_app.constants import COURSEID, NOTE_SUMMARY, NOTEID, TOPIC_SUMMARY, USERID, NOTE

api = Namespace('summary')


create_topic_summary_parser = api.parser()

create_topic_summary_parser.add_argument(USERID, location='form',
                        type=str, required=True,
                        help='Supabase ID of the user')
create_topic_summary_parser.add_argument(COURSEID, location='form',
                        type=str, required=True,
                        help='Course ID associated with the summary')

@api.expect(create_topic_summary_parser)
@api.route('/generate-topic-summary/<string:topicId>')
class GenerateTopicSummary(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self, topicId):
        args = create_topic_summary_parser.parse_args()
        userId = args.get(USERID, None)
        courseId = args.get(COURSEID, None)
        reqUserId = g.user_id

        logging.info(f"Generate topic summary for topicId: {topicId}, userId: {userId}, courseId: {courseId}")

        if (not HelperService.validate_all_uuid4(userId, courseId, topicId, reqUserId)
            or not SupabaseService.param_id_exists('courseId', courseId)
            or not SupabaseService.param_id_exists('userId', userId)
        ):
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}, topicId: {topicId}")
            return {'message': 'Must have userId, courseId, and topicId'}, 400
        
        if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=userId):
            logging.error(f"User {userId} is not authorized to create a summary for user {reqUserId}")
            return {'message': 'You do not have permission to create a summary for this user'}, 400
        
        if RatelimitService.is_rate_limited(userId, TOPIC_SUMMARY):
            logging.error(f"User {reqUserId} has exceeded their topic summary rate limit")
            return {'message': 'You have exceeded your topic summary rate limit'}, 400
        
        rateLimitId = RatelimitService.add_rate_limit(userId, TOPIC_SUMMARY, 1)
        
        SummaryService.generate_topic_summary(
            userId=userId, 
            courseId=courseId,
            topicId=topicId,
            rateLimitId=rateLimitId
            )
        
        return {'message': 'Summary generating'}, 200

create_note_summary_parser = api.parser()

create_note_summary_parser.add_argument(USERID, location='form',
                        type=str, required=True,
                        help='Supabase ID of the user')
create_note_summary_parser.add_argument(COURSEID, location='form',
                        type=str, required=True,
                        help='Course ID associated with the summary')  

@api.expect(create_note_summary_parser)
@api.route('/generate-note-summary/<string:noteId>')
class GenerateNoteSummary(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self, noteId):
        try:
            args = create_note_summary_parser.parse_args()
            userId = args.get(USERID, None)
            courseId = args.get(COURSEID, None)
            reqUserId = g.user_id

            if (
                not HelperService.validate_all_uuid4(userId, courseId, noteId, reqUserId)
            ):
                logging.error(f"Invalid userId: {userId}, courseId: {courseId}, noteId: {noteId}")
                return {'message': 'Must have userId, courseId, and noteId'}, 400
            
            if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=userId):
                logging.error(f"User {userId} is not authorized to create a summary for user {reqUserId}")
                return {'message': 'You do not have permission to create a summary for this user'}, 400
            
            if RatelimitService.is_rate_limited(userId, NOTE_SUMMARY):
                logging.error(f"User {reqUserId} has exceeded their note summary rate limit")
                return {'message': 'You have exceeded your note summary rate limit'}, 400
            
            rateLimitId = RatelimitService.add_rate_limit(userId, NOTE_SUMMARY, 1)
            
            SummaryService.generate_note_summary(
                userId=userId, 
                courseId=courseId,
                noteId=noteId,
                specifierParam=NOTEID,
                rateLimitId=rateLimitId
                )
            
            logging.info(f"Generated note summary for userId: {userId}, courseId: {courseId}, noteId: {noteId}, specifierParam: {NOTEID}")
        except Exception as e:
            logging.exception(f"Error generating note summary: {str(e)}")
            return {'message': str(e)}, 500
    
@api.route('/get-summary-for/<string:param>/<string:id>')
class GetSummaryFor(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, param, id):
        try:
            logging.info(f"Get summary for param: {param}, id: {id}")
            summaries = GraphQueryService.get_summary_for_param(param=param, id=id)
            logging.info(f"Summaries: {summaries}")
            return summaries
        except Exception as e:
            logging.exception(f"Error getting summary for {param} {id}: {str(e)}")
            return {'message': str(e)}, 500
    
@api.route('/get-summary-for-topic/<string:topicId>')
class GetSummaryForTopic(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, topicId):
        try:
            logging.info(f"Get summary for topicId: {topicId}")
            return GraphQueryService.get_topic_summary(uuid=topicId)
        except Exception as e:
            logging.exception(f"Error getting summary for topic {topicId}: {str(e)}")
            return {'message': str(e)}, 500