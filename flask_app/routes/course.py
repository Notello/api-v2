import logging
from flask_restx import Namespace, Resource
from flask import g

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.GraphDeletionService import GraphDeletionService
from flask_app.services.AuthService import AuthService
from flask_app.routes.auth import authorizations
from flask_app.routes.middleware import token_required

api = Namespace('course', authorizations=authorizations)

@api.route('/delete-course/<string:course_id>')
class Course(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, course_id):
        try:
            userId = g.user_id

            if not AuthService.can_edit_course(userId, course_id):
                logging.error(f"User {userId} is not authorized to delete course {course_id}")
                api.abort(403, f"You do not have permission to delete this course")

            notes = SupabaseService.get_noteIds_for_course(course_id)
            SupabaseService.delete_course(course_id)

            GraphDeletionService.delete_node_for_param('courseId', course_id)
            for note in notes:
                GraphDeletionService.delete_node_for_param('noteId', note['id'])

            logging.info(f"Course {course_id} deleted successfully")
            return {'message': 'Course deleted successfully'}, 200
        except Exception as e:
            logging.exception(f"Error deleting course {course_id}: {str(e)}")
            api.abort(500, f"An error occurred: {str(e)}")