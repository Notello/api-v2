from flask import request
from flask_restx import Namespace, Resource

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.GraphDeletionService import GraphDeletionService
from flask_app.services.AuthService import AuthService

from flask_app.routes.middleware import token_required

api = Namespace('user')


@api.route('/delete-user/<string:user_id>')
class Note(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, user_id):
        try:
            reqUserId = request.user_id

            if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=user_id):
                return {'message': 'unauthorized'}, 401

            notes = SupabaseService.get_notes_for_user(user_id)
            SupabaseService.delete_user(user_id)

            for note in notes:
                GraphDeletionService.delete_node_for_param('noteId', note['id'])
            
            return {'message': 'delete user'}, 200
        except Exception as e:
            return {'message': str(e)}, 500