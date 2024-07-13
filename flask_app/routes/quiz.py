import ast
import json
import logging
from flask_restx import Namespace, Resource

from flask_app.services.QuizService import QuizService
from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread

api = Namespace('quiz')


create_quiz_parser = api.parser()

create_quiz_parser.add_argument('userId', location='form', 
                        type=str, required=True,
                        help='Supabase ID of the user')
create_quiz_parser.add_argument('courseId', location='form', 
                        type=str, required=True,
                        help='Course ID associated with the quiz')
create_quiz_parser.add_argument('noteId', location='form', 
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
class GenerateQuizFor(Resource):
    def post(self):
        args = create_quiz_parser.parse_args()
        userId = args.get('userId', None)
        courseId = args.get('courseId', None)
        noteId = args.get('noteId', None)
        specifierParam = args.get('specifierParam', None)
        difficulty = args.get('difficulty', 3)
        numQuestions = args.get('numQuestions', 5)

        topics = args.get('topics', None)

        if topics is None:
            topics = []

        if (
            not HelperService.validate_all_uuid4(userId, courseId) \
            or (specifierParam is not None and specifierParam not in QuizService.validSpecifiers)
            or (not HelperService.validate_uuid4(noteId) and specifierParam == 'noteId')
            or not isinstance(topics, list)
                
        ):
            return {'message': 'Must have userId, courseId, optionally noteId and a valid specifierParam'}, 400
                
        quizId = SupabaseService.create_quiz(
            noteId=noteId,
            courseId=courseId,
            userId=userId,
            difficulty=difficulty,
            numQuestions=numQuestions
        )

        if quizId is None:
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
                      specifierParam
                      )
        ).start()

        return {'quizId': quizId}, 201
    
@api.route('/get-questions-for/<string:quizId>')
class GetQuestionsFor(Resource):
    def post(self, quizId):
        questions = GraphQueryService.get_quiz_questions_by_id(quizId=quizId)
        return {'questions': questions}, 200