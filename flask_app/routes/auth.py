from flask_restx import Namespace, Resource

from flask_app.services.SupabaseService import SupabaseService


authorizations = {
    "jsonWebToken": {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization"
    }
}

api = Namespace('auth')

@api.route('/login/<string:email>/<string:password>')
class Login(Resource):
    def get(self, email, password):
        try:
            user, session = SupabaseService.get_user(email, password)
            print(session)
            return session[1].access_token
        except Exception as e:
            return {'message': str(e)}, 500
        