import logging
from flask_restx import Namespace, Resource

from flask_app.services.QuizService import QuizService
from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService

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
create_quiz_parser.add_argument('difficulty', location='form', 
                        type=str, required=False,
                        help='Difficulty of the quiz from 1 - 5')
create_quiz_parser.add_argument('numQuestions', location='form', 
                        type=str, required=False,
                        help='Number of questions to generate')
create_quiz_parser.add_argument('topics', location='form', 
                        type=list, required=False,
                        help='List of topics to generate quiz for')

@api.expect(create_quiz_parser)
@api.route('/generate-quiz')
class GenerateQuizFor(Resource):
    def post(self):
        args = create_quiz_parser.parse_args()
        userId = args.get('userId', None)
        courseId = args.get('courseId', None)
        noteId = args.get('noteId', None)
        difficulty = args.get('difficulty', 3)
        numQuestions = args.get('numQuestions', 5)
        topics = args.get('topics', None)

        if (not HelperService.validate_uuid4(noteId)) and (topics is None or len(topics) == 0):
            return {'message': 'Either noteId or topics must be provided'}, 400

        if not HelperService.validate_uuid4(courseId, userId):
            return {'message': 'Invalid courseId or userId'}, 400
        
        quiz = SupabaseService.create_quiz(
            noteId=noteId,
            courseId=courseId,
            userId=userId,
            difficulty=difficulty,
            numQuestions=numQuestions
        )
        
        # if topics:
        #     topic_graph = GraphQueryService.get_topic_graph_from_topic_list(
        #         topics=topics
        #         )

        #     quiz = QuizService.generate_quiz(
        #         topic_graph=topic_graph,
        #         courseId=courseId, 
        #         userId=userId, 
        #         noteId=noteId
        #         )
        # else:
        #     topic_graph = GraphQueryService.get_topic_graph_from_param(
        #         param="noteId", 
        #         id=noteId
        #         )

        #     quiz = QuizService.generate_quiz(
        #         topics, 
        #         courseId, 
        #         userId, 
        #         noteId
        #         )

        # quiz = QuizService.generate_quiz_for_param(param, id)
        return {'message': 'Not implemented'}, 200
    
@api.route('/get-questions-for/<string:quizId>')
class GenerateQuizFor(Resource):
    def post(self, quizId):
        quiz = QuizService.get_quiz_for_param(quizId)
        return {'message': 'Not implemented'}, 200