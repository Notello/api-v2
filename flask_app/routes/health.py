import os
from flask_restx import Namespace, Resource

from flask_app.constants import K8S_VER

from flask_app.src.shared.common_fn import get_graph

api = Namespace('health')

@api.route('/ping')
class Health(Resource):
    def get(self):
        return {'message': 'pong'}, 200
    
@api.route('/version')
class Health(Resource):
    def get(self):
        return {'message': K8S_VER}, 200
    
@api.route('/db')
class Health(Resource):
    def get(self):
        try:
            from flask_app.src.graphDB_dataAccess import graphDBdataAccess
            graphAccess = graphDBdataAccess(get_graph())
            working = graphAccess.connection_check()

            if not working:
                return {'message': 'DB is down'}, 500

            return {'message': 'DB is up'}, 200
        except Exception as e:
            return {'message': str(e)}, 500

@api.route('/env-type')
class Health(Resource):
    def get(self):
        return {'message': os.getenv('ENV_TYPE')}, 200