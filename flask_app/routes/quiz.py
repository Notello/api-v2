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

from flask_app.routes.middleware import token_required
from flask_app.constants import COURSEID, NOTEID, QUIZ, USERID, QUIZID

logging.basicConfig(format='%(asctime)s - %(message)s', level='INFO')

api = Namespace('quiz')

create_quiz_parser = api.parser()

create_quiz_parser.add_argument(USERID, location='form', 
                        type=str, required=True,
                        help='Supabase ID of the user')
create_quiz_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the quiz')
create_quiz_parser.add_argument(NOTEID, location='form', 
                        type=str, required=False,
                        help='Note ID associated with the quiz, if not provided a topic list is required')
create_quiz_parser.add_argument('specifierParam', location='form',
                                type=str, required=False,
                                help='Which id to use to specify the topic for quiz generation')
create_quiz_parser.add_argument('difficulty', location='form', 
                        type=int, required=False,
                        help='Difficulty of the quiz from 1 - 5')
create_quiz_parser.add_argument('numQuestions', location='form', 
                        type=int, required=False,
                        help='Number of questions to generate')
create_quiz_parser.add_argument('topics', location='form', action='split')

@api.expect(create_quiz_parser)
@api.route('/generate-quiz')
class GenerateQuiz(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_quiz_parser.parse_args()
            userId = args.get(USERID, None)
            courseId = args.get(COURSEID, None)
            noteId = args.get(NOTEID, None)
            specifierParam = args.get('specifierParam', None)
            difficulty = args.get('difficulty', 3)
            numQuestions = args.get('numQuestions', 5)
            topics = args.get('topics', None)
            reqUserId = g.user_id

            logging.info(f"Generate quiz for userId: {userId}, courseId: {courseId}, noteId: {noteId}, specifierParam: {specifierParam}, difficulty: {difficulty}, numQuestions: {numQuestions}, topics: {topics}")

            if topics is None:
                topics = []

            if (
                not HelperService.validate_all_uuid4(userId, courseId) \
                or (specifierParam is not None and specifierParam not in QuizService.validSpecifiers)
                or (not HelperService.validate_uuid4(noteId) and specifierParam == NOTEID)
                or not isinstance(topics, list)
                or not SupabaseService.param_id_exists(COURSEID, courseId)
                or not SupabaseService.param_id_exists(USERID, userId)
                or (noteId is not None and not SupabaseService.param_id_exists('noteId', noteId))
            ):
                logging.error(f"Invalid userId: {userId}, courseId: {courseId}, noteId: {noteId}, specifierParam: {specifierParam}")
                return {'message': 'Must have userId, courseId, optionally noteId and a valid specifierParam'}, 400
            
            if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=userId):
                logging.error(f"User {userId} is not authorized to create a quiz for user {reqUserId}")
                return {'message': 'You do not have permission to create a quiz for this user'}, 400

            if RatelimitService.is_rate_limited(userId, QUIZ):
                logging.error(f"User {reqUserId} has exceeded their quiz rate limit")
                return {'message': 'You have exceeded your quiz rate limit'}, 400
            
            rateLimitId = RatelimitService.add_rate_limit(userId, QUIZ, numQuestions)
                    
            quizId = SupabaseService.create_quiz(
                noteId=noteId,
                courseId=courseId,
                userId=userId,
                difficulty=difficulty,
                numQuestions=numQuestions
            )

            if quizId is None:
                logging.error(f"Quiz creation failed for userId: {userId}, courseId: {courseId}, noteId: {noteId}, specifierParam: {specifierParam}, difficulty: {difficulty}, numQuestions: {numQuestions}, topics: {topics}")
                return {'message': 'Quiz creation failed'}, 400

            ContextAwareThread(
                    target=QuizService.generate_quiz,
                    args=(topics, 
                        courseId, 
                        userId, 
                        quizId, 
                        noteId,
                        difficulty,
                        numQuestions,
                        specifierParam,
                        rateLimitId
                        )
            ).start()

            return {'quizId': quizId}, 201
        except Exception as e:
            logging.exception(f"Error generating quiz: {str(e)}")
            return {'message': str(e)}, 500
    
@api.route('/get-questions-for/<string:quizId>')
class GetQuestionsFor(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self, quizId):
        try:
            logging.info(f"Get questions for quizId: {quizId}")
            questions = GraphQueryService.get_quiz_questions_by_id(quizId=quizId)
            
            logging.info(f"Got {len(questions)} questions for quizId: {quizId}")
            return {'questions': questions}, 200
        except Exception as e:
            logging.exception(f"Error getting questions for quiz {quizId}: {str(e)}")
            return {'message': str(e)}, 500

complete_quiz_parser = api.parser()
complete_quiz_parser.add_argument(USERID, location='form', 
                        type=str, required=True,
                        help='Supabase ID of the user')
complete_quiz_parser.add_argument('results', location='form', type=str, required=True,
                        help='Dictionary of UUID to boolean results')

@api.route('/complete-quiz/<string:quizId>')
class CompleteQuiz(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    @api.expect(complete_quiz_parser)
    def post(self, quizId):
        try:
            args = complete_quiz_parser.parse_args()
            userId = args.get(USERID, None)
            results = args.get('results', None)
            reqUserId = g.user_id

            results = json.loads(results)

            logging.info(f"Complete quiz for userId: {userId}, quizId: {quizId}, results: {results}")
            
            if not AuthService.is_authed_for_userId(reqUserId, userId):
                logging.error(f"User {userId} is not authorized to complete quiz {quizId}")
                return {'message': 'You do not have permission to complete this quiz'}, 400
            
            if not SupabaseService.param_id_exists(QUIZID, quizId):
                logging.error(f"Quiz {quizId} does not exist")
                return {'message': 'Quiz does not exist'}, 400
            
            for uuid, result in results.items():
                if not isinstance(result, bool) or not HelperService.validate_uuid4(uuid):
                    return {'message': f'Invalid result for UUID {uuid}. Must be a valid UUID boolean mapping'}, 400
            
            GraphCreationService.insert_question_results(userId=userId, results=results)

            return {'message': 'Quiz completed'}, 200
        except Exception as e:
            logging.exception(f"Error completing quiz: {str(e)}")
            return {'message': str(e)}, 500