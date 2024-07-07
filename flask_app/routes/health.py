from flask_restx import Namespace, Resource

api = Namespace('health')

@api.route('/ping')
class Health(Resource):
    def get(self):
        return {'message': 'pong'}, 200