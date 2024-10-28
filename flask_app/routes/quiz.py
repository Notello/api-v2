from concurrent.futures import ThreadPoolExecutor
import json
import logging
from flask_restx import Namespace, Resource
from flask import request

from flask_app.services.QuizServiceNew import QuizServiceNew


from flask_app.routes.middleware import token_required
from flask_app.routes.auth import authorizations

from flask_app.constants import COURSEID, NOTEID, QUIZ, USERID

logging.basicConfig(format='%(asctime)s - %(message)s', level='INFO')

pthread = ThreadPoolExecutor(max_workers=10)

api = Namespace('quiz', authorizations=authorizations)

create_quiz_parser = api.parser()

create_quiz_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the quiz')
create_quiz_parser.add_argument(NOTEID, location='form', 
                        type=str, required=True,
                        help='Note ID associated with the quiz, if not provided a topic list is required')
create_quiz_parser.add_argument('nodeId', location='form', 
                        type=str, required=True,
                        help='Id of the quiz Node to generate.')

@api.expect(create_quiz_parser)
@api.route('/generate-node-quiz')
class GenerateQuiz(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_quiz_parser.parse_args()
            courseId = args.get(COURSEID, None)
            noteId = args.get(NOTEID, None)
            nodeId = args.get("nodeId", None)

            QuizServiceNew.generate_questions_for_node(
                nodeId=nodeId,
                noteId=noteId,
                courseId=courseId
            )

            return {'message': 'complete'}, 201
        except Exception as e:
            logging.exception(f"Error generating quiz: {str(e)}")
            return {'message': str(e)}, 500

grade_frq_question = api.parser()

grade_frq_question.add_argument('question', location='form', 
                        type=str, required=True,
                        help='Question to access based on')
grade_frq_question.add_argument('answer', location='form', 
                        type=str, required=True,
                        help='User answer')
grade_frq_question.add_argument('mainConceptId', location='form', 
                        type=str, required=True,
                        help='Main concept')
grade_frq_question.add_argument('mainConceptName', location='form', 
                        type=str, required=True,
                        help='Main concept')
create_quiz_parser.add_argument(NOTEID, location='form', 
                        type=str, required=True,
                        help='Note ID associated with the quiz, if not provided a topic list is required')
create_quiz_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the quiz')


@api.expect(grade_frq_question)
@api.route('/grade-frq-question')
class GradeFrqQuestion(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = grade_frq_question.parse_args()
            question = args.get("question", None)
            answer = args.get("answer", None)
            mainConceptId = args.get("mainConceptId", None)
            mainConceptName = args.get("mainConceptName", None)
            noteId = args.get(NOTEID, None)
            courseId = args.get(COURSEID, None)

            response = QuizServiceNew.grade_frq_question(
                question=question,
                answer=answer,
                mainConceptId=mainConceptId,
                mainConceptName=mainConceptName,
                noteId=noteId,
                courseId=courseId
            )

            return response, 200
        except Exception as e:
            logging.exception(f"Error generating quiz: {str(e)}")
            return {'message': str(e)}, 500