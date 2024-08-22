import os
from flask_restx import Namespace, Resource

from flask_app.src.graphDB_dataAccess import graphDBdataAccess

from flask_app.constants import K8S_VER


api = Namespace('health')

@api.route('/version')
class Health(Resource):
    def get(self):
        return {'message': K8S_VER}, 200

@api.route('/env-type')
class Health(Resource):
    def get(self):
        return {'message': os.getenv('ENV_TYPE')}, 200

@api.route('/ping')
class Health(Resource):
    def get(self):
        return {'message': 'pong'}, 200
    
@api.route('/db')
class Health(Resource):
    def get(self):
        try:
            graphAccess = graphDBdataAccess()
            working = graphAccess.connection_check()

            if not working:
                return {'message': 'DB is down'}, 500

            return {'message': 'DB is up'}, 200
        except Exception as e:
            return {'message': str(e)}, 500