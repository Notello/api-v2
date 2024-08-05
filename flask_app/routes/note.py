from flask_restx import Namespace, Resource

from flask_app.services.GraphDeletionService import GraphDeletionService
from flask_app.services.SupabaseService import SupabaseService

api = Namespace('note')


@api.route('/delete-note/<string:note_id>')
class Note(Resource):
    def get(self, note_id):
        try:
            SupabaseService.delete_note(note_id)
            GraphDeletionService.delete_node_for_param('noteId', note_id)
            return {'message': 'delete note'}, 200
        except Exception as e:
            return {'message': str(e)}, 500