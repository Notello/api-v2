import logging
from flask_restx import Namespace, Resource
from flask import request

from flask_app.services.RecommendationService import RecommendationService

from flask_app.routes.middleware import token_required
from flask_app.routes.auth import authorizations

from flask_app.constants import COURSEID

logging.basicConfig(format='%(asctime)s - %(message)s', level='INFO')

api = Namespace('rec', authorizations=authorizations)

rec_note_for_user_parser = api.parser()
rec_note_for_user_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the user')

@api.expect(rec_note_for_user_parser)
@api.route('/get-notes-for-user')
class RecommendNotesForUser(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = rec_note_for_user_parser.parse_args()
            courseId = args.get(COURSEID, None)
            userId = request.user_id

            logging.info(f"Get notes for userId: {userId}, courseId: {courseId}")
            
            recommendedNotes = RecommendationService.get_recommended_notes_for_user(userId=userId, courseId=courseId)

            logging.info(f"Got {len(recommendedNotes)} notes for userId: {userId}, courseId: {courseId}")
            return recommendedNotes, 200
        except Exception as e:
            logging.exception(f"Error getting notes for user {userId}: {str(e)}")
            return {'message': str(e)}, 500

rec_topic_parser = api.parser()
rec_topic_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the user')
  
@api.expect(rec_topic_parser)
@api.route('/get-topics-to-study')
class RecommendTopicsToStudy(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = rec_topic_parser.parse_args()
            courseId = args.get(COURSEID, None)
            userId = request.user_id

            logging.info(f"Get topics to study for userId: {userId}, courseId: {courseId}")
            
            recommendedTopics = RecommendationService.get_recommended_topics_for_user(userId=userId, courseId=courseId)

            logging.info(f"Got {len(recommendedTopics)} topics for userId: {userId}, courseId: {courseId}")
            return recommendedTopics, 200
        except Exception as e:
            logging.exception(f"Error getting topics to study for user {userId}: {str(e)}")
            return {'message': str(e)}, 500