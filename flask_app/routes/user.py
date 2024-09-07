import logging
from flask import request
from flask_restx import Namespace, Resource

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.GraphDeletionService import GraphDeletionService
from flask_app.services.AuthService import AuthService

from flask_app.routes.middleware import token_required
from flask_app.routes.auth import authorizations

api = Namespace('user', authorizations=authorizations)

delete_user_parser = api.parser()
delete_user_parser.add_argument('delete_notes', type=bool, required=True, help='Whether to delete notes associated with the user')

@api.route('/delete-user/<string:user_id>')
class Note(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self, user_id):
        try:
            args = delete_user_parser.parse_args()
            delete_notes = args.get('delete_notes', False)
            reqUserId = request.user_id

            if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=user_id):
                return {'message': 'unauthorized'}, 401
            

            notes = SupabaseService.get_notes_for_user(user_id)
            SupabaseService.delete_user(user_id)

            form_dict = {
                'audio': 'audio-files',
                'text-file': 'pdf-files'
            }

            if delete_notes:
                for note in notes:
                    GraphDeletionService.delete_node_for_param('noteId', note['id'])
                    SupabaseService.delete_note(noteId=note['id'], bucketName=form_dict.get(note['form'], None))
            
            return {'message': 'delete user'}, 200
        except Exception as e:
            logging.exception(f"Error deleting user {user_id}: {str(e)}")
            return {'message': str(e)}, 500