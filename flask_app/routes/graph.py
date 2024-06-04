import asyncio
import logging
from flask_restx import Namespace, Resource

from flask_app.services.NoteService import NoteService
from flask_app.src.main import create_source_node_graph_url_youtube


api = Namespace('graph')

parser = api.parser()
parser.add_argument('youtube_url',
                        type=str, required=True,
                        help='Youtube url')
parser.add_argument('user_id',
                        type=str, required=True,
                        help='Supabase id of the user')
parser.add_argument('course_id',
                        type=str, required=True,
                        help='Id of the course to add the note to')

@api.expect(parser)
@api.route('/intake-youtube')
class GraphRoute(Resource):
    def post(self):
        try:
            print('inside graph route')

            args = parser.parse_args()
            youtube_url = args['youtube_url']
            courseId = args['course_id']
            userId = args['user_id']

            if youtube_url is None or courseId is None or userId is None:
                message = f"Args missing youtube_url: {youtube_url}, courseId: {courseId}, userId: {userId}"
                return {'message':message}, 400
            
            noteId = NoteService.create_note(
                courseId=courseId, 
                userId=userId, 
                form='youtube', 
                audio_file=youtube_url, 
                keywords=''
                )

            lst_file_name,success_count,failed_count = create_source_node_graph_url_youtube(
                source_url=youtube_url, 
                noteId=noteId, 
                courseId=courseId,
                userId=userId
                )

            print(f"lst_file_name:{lst_file_name}")
            print(f"success_count:{success_count}")
            print(f"failed_count:{failed_count}")

            message = f"Source Node created successfully for source type: youtube and source: {youtube_url}"

            return {
                'message': message, 
                'success_count': success_count,
                'failed_count': failed_count,
                'file_name_list': lst_file_name}, 200
        except Exception as e:
            error_message = str(e)
            message = f" Unable to create source node for source type: youtube and source: {youtube_url}"
            logging.exception(f'Exception Stack trace:')
            return {'message': message}, 200