from flask_restx import Resource, Namespace

api = Namespace('whisper')

@api.route('/')
class Whisper(Resource):
    def get(self):
        return 'Whisper'