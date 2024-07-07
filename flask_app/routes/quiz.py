import logging
from flask_restx import Namespace, Resource

from flask_app.services.QuizService import QuizService

api = Namespace('quiz')

@api.route('/generate-quiz-for/<string:param>/<string:id>')
class GenerateQuizFor(Resource):
    def post(self, param, id):
        QuizService.generate_quiz_for_param(param, id)
        return {'message': 'Not implemented'}, 200
    
@api.route('/generate-quiz-for-topic-list')
class GenerateQuizFor(Resource):
    def post(self):
        QuizService.generate_quiz_for_topic_list()
        return {'message': 'Not implemented'}, 200
    
@api.route('/get-quiz-for/<string:param>/<string:id>')
class GenerateQuizFor(Resource):
    def post(self, param, id):
        QuizService.get_quiz_for_param(param, id)
        return {'message': 'Not implemented'}, 200