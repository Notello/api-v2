import logging
from flask_restx import Namespace, Resource
from flask import g

from flask_app.services.GraphDeletionService import GraphDeletionService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.AuthService import AuthService
from flask_app.routes.middleware import token_required



api = Namespace('note')


@api.route('/delete-note/<string:note_id>')
class Note(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, note_id):
        try:
            userId = g.user_id

            if not AuthService.can_edit_note(userId, note_id):
                logging.error(f"User {userId} is not authorized to delete note {note_id}")
                api.abort(403, f"You do not have permission to delete this note")

            SupabaseService.delete_note(note_id)
            GraphDeletionService.delete_node_for_param('noteId', note_id)
            logging.info(f"Note {note_id} deleted successfully")
            return {'message': 'delete note'}, 200
        except Exception as e:
            logging.exception(f"Error deleting note {note_id}: {str(e)}")
            return {'message': str(e)}, 500