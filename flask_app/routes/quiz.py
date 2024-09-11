import json
import logging
from flask_restx import Namespace, Resource
from flask import request

from flask_app.services.QuizService import QuizService
from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.RatelimitService import RatelimitService
from flask_app.services.GraphCreationService import GraphCreationService

from flask_app.routes.middleware import token_required
from flask_app.routes.auth import authorizations

from flask_app.constants import COURSEID, NOTEID, QUIZ, USERID

logging.basicConfig(format='%(asctime)s - %(message)s', level='INFO')

api = Namespace('quiz', authorizations=authorizations)

create_quiz_parser = api.parser()

create_quiz_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the quiz')
create_quiz_parser.add_argument(NOTEID, location='form', 
                        type=str, required=False,
                        help='Note ID associated with the quiz, if not provided a topic list is required')
create_quiz_parser.add_argument('difficulty', location='form', 
                        type=int, required=False,
                        help='Difficulty of the quiz from 1 - 5')
create_quiz_parser.add_argument('numQuestions', location='form', 
                        type=int, required=False,
                        help='Number of questions to generate')
create_quiz_parser.add_argument('topics', location='form', 
                        type=str, required=False,
                        help='Topics to focus quiz on')

@api.expect(create_quiz_parser)
@api.route('/generate-quiz')
class GenerateQuiz(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_quiz_parser.parse_args()
            courseId = args.get(COURSEID, None)
            noteId = args.get(NOTEID, None)
            difficulty = args.get('difficulty', 3)
            numQuestions = args.get('numQuestions', 5)
            topics = args.get('topics', None)

            logging.info(f"Topics: {topics}")

            topics = [] if not topics else topics.split(',')
            topicsFiltered = [t for t in topics if t is not None]
            userId = request.user_id

            specifierParam = NOTEID if noteId else COURSEID

            logging.info(f"Specifier param: {specifierParam}, noteId: {noteId}")

            logging.info(f"Topics: {topicsFiltered}")

            if (
                not HelperService.validate_all_uuid4(userId, courseId) \
                or (specifierParam is not None and specifierParam not in QuizService.validSpecifiers)
                or (not HelperService.validate_uuid4(noteId) and specifierParam == NOTEID)
                or not isinstance(topicsFiltered, list)
                or not SupabaseService.param_id_exists(COURSEID, courseId)
                or not SupabaseService.param_id_exists(USERID, userId)
                or (noteId is not None and not SupabaseService.param_id_exists('noteId', noteId))
            ):
                logging.error(f"Invalid userId: {userId}, courseId: {courseId}, noteId: {noteId}, specifierParam: {specifierParam}")
                return {'message': 'Must have userId, courseId, optionally noteId and a valid specifierParam'}, 400

            if RatelimitService.is_rate_limited(userId, QUIZ):
                logging.error(f"User {userId} has exceeded their quiz rate limit")
                return {'message': 'You have exceeded your quiz rate limit'}, 250
                    
            quizId = SupabaseService.create_quiz(
                noteId=noteId,
                courseId=courseId,
                userId=userId,
                difficulty=difficulty,
                numQuestions=numQuestions
            )

            if quizId is None:
                logging.error(f"Quiz creation failed for userId: {userId}, courseId: {courseId}, noteId: {noteId}, specifierParam: {specifierParam}, difficulty: {difficulty}, numQuestions: {numQuestions}, topics: {topicsFiltered}")
                return {'message': 'Quiz creation failed'}, 400

            ContextAwareThread(
                    target=QuizService.generate_quiz,
                    args=(topicsFiltered, 
                        courseId, 
                        userId, 
                        quizId, 
                        noteId,
                        difficulty,
                        numQuestions,
                        specifierParam
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
            results = args.get('results', None)
            userId = request.user_id

            results = json.loads(results)

            logging.info(f"Complete quiz for userId: {userId}, quizId: {quizId}, results: {results}")

            for result in results:
                if not isinstance(result['result'], bool) or not HelperService.validate_uuid4(result['uuid']):
                    return {'message': f'Invalid result for UUID {result["uuid"]}. Must be a valid UUID boolean mapping'}, 400
            
            GraphCreationService.insert_question_results(userId=userId, results=results)

            return {'message': 'Quiz completed'}, 200
        except Exception as e:
            logging.exception(f"Error completing quiz: {str(e)}")
            return {'message': str(e)}, 500