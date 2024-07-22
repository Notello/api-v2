from flask_restx import Namespace, Resource

from flask_app.constants import K8S_VER

api = Namespace('health')

@api.route('/ping')
class Health(Resource):
    def get(self):
        return {'message': 'pong'}, 200
    
@api.route('/version')
class Health(Resource):
    def get(self):
        return {'message': K8S_VER}, 200