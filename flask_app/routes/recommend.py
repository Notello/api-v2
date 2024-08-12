import json
import logging
from flask_restx import Namespace, Resource
from flask import g

from flask_app.services.QuizService import QuizService
from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.RatelimitService import RatelimitService
from flask_app.services.AuthService import AuthService
from flask_app.services.GraphCreationService import GraphCreationService
from flask_app.services.RecommendationService import RecommendationService

from flask_app.routes.middleware import token_required
from flask_app.routes.auth import authorizations
from flask_app.constants import COURSEID, NOTEID, QUIZ, USERID, QUIZID

logging.basicConfig(format='%(asctime)s - %(message)s', level='INFO')

api = Namespace('rec', authorizations=authorizations)

rec_note_for_user_parser = api.parser()
rec_note_for_user_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the user')

@api.expect(rec_note_for_user_parser)
@api.route('/get-notes-for-user/<string:userId>')
class RecommendNotesForUser(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self, userId):
        try:
            args = rec_note_for_user_parser.parse_args()
            courseId = args.get(COURSEID, None)
            reqUserId = g.user_id

            logging.info(f"Get notes for userId: {userId}, courseId: {courseId}")
            
            if not AuthService.is_authed_for_userId(reqUserId, userId):
                logging.error(f"User {userId} is not authorized to get notes for user {reqUserId}")
                return {'message': 'You do not have permission to get notes for this user'}, 400
            
            if not SupabaseService.param_id_exists(COURSEID, courseId):
                logging.error(f"Course {courseId} does not exist")
                return {'message': 'Course does not exist'}, 400
            
            recommendedNotes = RecommendationService.get_recommended_notes_for_user(userId=userId, courseId=courseId)

            logging.info(f"Got {len(recommendedNotes)} notes for userId: {userId}, courseId: {courseId}")
            return {'notes': recommendedNotes}, 200
        except Exception as e:
            logging.exception(f"Error getting notes for user {userId}: {str(e)}")
            return {'message': str(e)}, 500

rec_topic_parser = api.parser()
rec_topic_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the user')
  
@api.expect(rec_topic_parser)
@api.route('/get-topics-to-study/<string:userId>')
class RecommendTopicsToStudy(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self, userId):
        try:
            args = rec_topic_parser.parse_args()
            courseId = args.get(COURSEID, None)
            reqUserId = g.user_id

            logging.info(f"Get topics to study for userId: {userId}, courseId: {courseId}")
            
            if not AuthService.is_authed_for_userId(reqUserId, userId):
                logging.error(f"User {userId} is not authorized to get topics to study for user {reqUserId}")
                return {'message': 'You do not have permission to get topics to study for this user'}, 400
            
            if not SupabaseService.param_id_exists(COURSEID, courseId):
                logging.error(f"Course {courseId} does not exist")
                return {'message': 'Course does not exist'}, 400
            
            recommendedTopics = RecommendationService.get_recommended_topics_for_user(userId=userId, courseId=courseId)

            logging.info(f"Got {len(recommendedTopics)} topics for userId: {userId}, courseId: {courseId}")
            return {'topics': recommendedTopics}, 200
        except Exception as e:
            logging.exception(f"Error getting topics to study for user {userId}: {str(e)}")
            return {'message': str(e)}, 500