from flask_restx import Namespace, Resource

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.GraphDeletionService import GraphDeletionService

api = Namespace('user')


@api.route('/delete-user/<string:user_id>')
class Note(Resource):
    def get(self, user_id):
        try:
            notes = SupabaseService.get_notes_for_user(user_id)
            SupabaseService.delete_user(user_id)

            for note in notes:
                GraphDeletionService.delete_node_for_param('noteId', note['id'])
            
            return {'message': 'delete user'}, 200
        except Exception as e:
            return {'message': str(e)}, 500