import logging
from flask_restx import Namespace, Resource
from flask import request

from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SummaryService import SummaryService
from flask_app.services.RatelimitService import RatelimitService

from flask_app.routes.auth import authorizations
from flask_app.routes.middleware import token_required

from flask_app.constants import COURSEID, NOTE_SUMMARY, NOTEID, TOPIC_SUMMARY, USERID, NOTE, getSummaryKey

api = Namespace('summary', authorizations=authorizations)


create_topic_summary_parser = api.parser()

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
        courseId = args.get(COURSEID, None)
        userId = request.user_id

        logging.info(f"Generate topic summary for topicId: {topicId}, userId: {userId}, courseId: {courseId}")

        if not HelperService.validate_all_uuid4(userId, courseId, topicId):
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}, topicId: {topicId}")
            return {'message': 'Must have userId, courseId, and topicId'}, 400

        if RatelimitService.is_rate_limited(userId, TOPIC_SUMMARY):
            logging.error(f"User {userId} has exceeded their topic summary rate limit")
            return {'message': 'You have exceeded your topic summary rate limit'}, 400
                
        SummaryService.generate_topic_summary(
            userId=userId, 
            courseId=courseId,
            topicId=topicId,
            )
        
        return {'message': 'Summary generating'}, 200

create_note_summary_parser = api.parser()

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
            courseId = args.get(COURSEID, None)
            userId = request.user_id

            if (
                not HelperService.validate_all_uuid4(userId, courseId, noteId)
            ):
                logging.error(f"Invalid userId: {userId}, courseId: {courseId}, noteId: {noteId}")
                return {'message': 'Must have userId, courseId, and noteId'}, 400

            if RatelimitService.is_rate_limited(userId, NOTE_SUMMARY):
                logging.error(f"User {userId} has exceeded their note summary rate limit")
                return {'message': 'You have exceeded your note summary rate limit'}, 400
            
            logging.info(f"Generated note summary for userId: {userId}, courseId: {courseId}, noteId: {noteId}, specifierParam: {NOTEID}")
            
            SummaryService.generate_note_summary(
                userId=userId, 
                courseId=courseId,
                noteId=noteId,
                specifierParam=NOTEID,
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