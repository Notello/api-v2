from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from flask import current_app

from ..services.NoteService import NoteService

api = Namespace('')

file_upload = api.parser()
file_upload.add_argument('file', location='files',
                        type=FileStorage, required=True,
                        help='Audio file to be transcribed')
file_upload.add_argument('keywords', location='form', 
                        type=str, required=False,
                        help='Space-separated keywords to enhance transcription accuracy')
file_upload.add_argument('userId', location='form', 
                        type=str, required=True,
                        help='Supabase ID of the user')
file_upload.add_argument('courseId', location='form', 
                        type=str, required=True,
                        help='Course ID associated with the note')

@api.expect(file_upload)
@api.route('/create-audio-note')
class Whisper(Resource):
    def post(self):
        args = file_upload.parse_args()
        userId = args.get('userId', None)
        courseId = args.get('courseId', None)
        audio_file = args.get('file', None)
        keywords = args.get('keywords', None)

        noteId = NoteService.create_note(
            courseId=courseId,
            userId=userId,
            form='audio',
            audio_file=audio_file,
            keywords=keywords
        )

        if noteId is None:
            return {'message': 'Note creation failed'}, 400
        else:
            return {'message': 'Note created successfully', 'id': noteId}, 201