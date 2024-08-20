import logging
from flask import request
from flask_restx import Namespace, Resource
from werkzeug.datastructures import FileStorage


from flask_app.services.NoteService import NoteForm, NoteService, IngestType
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.AuthService import AuthService
from flask_app.services.ValidationService import ValidationService
from flask_app.services.GraphDeletionService import GraphDeletionService


from flask_app.constants import COURSEID, NOTE, NOTEID, USERID
from flask_app.routes.middleware import token_required

api = Namespace('note')

@api.route('/delete-note/<string:note_id>')
class Note(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def get(self, note_id: str):
        try:
            userId = request.user_id

            if not AuthService.can_edit_note(userId, note_id):
                logging.error(f"User {userId} is not authorized to delete note {note_id}")
                api.abort(403, f"You do not have permission to delete this note")

            NoteService.delete_note(note_id)
            GraphDeletionService.delete_node_for_param('noteId', note_id)
            logging.info(f"Note {note_id} deleted successfully")
            return {'message': 'delete note'}, 200
        except Exception as e:
            logging.exception(f"Error deleting note {note_id}: {str(e)}")
            return {'message': str(e)}, 500

intake_youtube_parser = api.parser()
intake_youtube_parser.add_argument('ingestType', location='form',
                        type=str, required=True,
                        help='edit or create')
intake_youtube_parser.add_argument('youtubeUrl', location='form',
                        type=str, required=True,
                        help='Youtube url')
intake_youtube_parser.add_argument(COURSEID, location='form',
                        type=str, required=True,
                        help='Id of the course to add the note to')
intake_youtube_parser.add_argument(NOTEID, location='form',
                        type=str, required=False,
                        help='Optional note ID to edit')

@api.expect(intake_youtube_parser)
@api.route('/intake-youtube')
class YoutubeIntake(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            logging.info('In youtube intake post')

            args = intake_youtube_parser.parse_args()
            youtubeUrl = args.get('youtubeUrl', None)
            courseId = args.get(COURSEID, None)
            noteId = args.get(NOTEID, None)
            ingestType = NoteService.ingest_to_enum(args.get('ingestType', None))
            userId = request.user_id

            logging.info(f"Youtube url: {youtubeUrl}")

            valid = ValidationService.validate_youtube_inputs(
                youtubeUrl=youtubeUrl,
                courseId=courseId,
                userId=userId,
                ingestType=ingestType
                )
            
            if not valid:
                return {'message': 'Invalid inputs'}, 400
            
            noteId = NoteService.ingest_note(
                courseId=courseId,
                userId=userId,
                noteId=noteId,
                ingestType=ingestType,
                form=NoteForm.YOUTUBE,
                sourceUrl=youtubeUrl
                )
            
            if not noteId:
                return {'message': 'Note creation failed'}, 400

            logging.info(f"Source Node created successfully for source type: youtube and source: {youtubeUrl}")

            return { NOTEID: noteId }, 201
        except Exception as e:
            message = f"Unable to create source node for source type: youtube, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400
        
create_audio_note_parser = api.parser()
create_audio_note_parser.add_argument('file', location='files',
                        type=FileStorage, required=True,
                        help='Audio file to be transcribed')
create_audio_note_parser.add_argument('ingestType', location='form', 
                        type=str, required=False,
                        help='edit or create')
create_audio_note_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the note')
create_audio_note_parser.add_argument(NOTEID, location='form', 
                        type=str, required=False,
                        help='Optional note ID to edit')

@api.expect(create_audio_note_parser)
@api.route('/create-audio-note')
class AudioIntake(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_audio_note_parser.parse_args()
            courseId = args.get(COURSEID, None)
            noteId = args.get(NOTEID, None)
            audio_file = args.get('file', None)
            ingestType = NoteService.ingest_to_enum(args.get('ingestType', None))
            userId = request.user_id

            valid = ValidationService.validate_audio_inputs(
                audio_file=audio_file,
                courseId=courseId,
                userId=userId,
                ingestType=ingestType
                )
            
            if not valid:
                return {'message': 'Invalid inputs'}, 400
            
            noteId = NoteService.ingest_note(
                courseId=courseId,
                userId=userId,
                noteId=noteId,
                form=NoteForm.AUDIO,
                ingestType=ingestType,
                file=audio_file,
                )
            
            if not noteId:
                return {'message': 'Note creation failed'}, 400
            
            logging.info(f"Source Node created successfully for source type: audio and source: {audio_file}")
            return { NOTEID: noteId }, 201
        except Exception as e:
            message = f"Unable to create source node for source type: audio and source: {audio_file}, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400
        
create_text_note_parser = api.parser()
create_text_note_parser.add_argument('rawText', location='form', 
                        type=str, required=True,
                        help='The raw text to ingest')
create_text_note_parser.add_argument('ingestType', location='form', 
                        type=str, required=True,
                        help='edit or create')
create_text_note_parser.add_argument('noteName', location='form', 
                        type=str, required=True,
                        help='The name of the note')
create_text_note_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the note')
create_text_note_parser.add_argument(NOTEID, location='form', 
                        type=str, required=False,
                        help='Optional note ID to edit')


@api.expect(create_text_note_parser)
@api.route('/create-text-note')
class TextIntake(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_text_note_parser.parse_args()
            courseId = args.get(COURSEID, None)
            noteId = args.get(NOTEID, None)
            rawText = args.get('rawText', None)
            noteName = args.get('noteName', None)
            ingestType = NoteService.ingest_to_enum(args.get('ingestType', None))
            userId = request.user_id

            valid = ValidationService.validate_text_inputs(
                rawText=rawText,
                noteName=noteName,
                courseId=courseId,
                userId=userId,
                ingestType=ingestType
                )
            
            if not valid:
                return {'message': 'Invalid inputs'}, 400
            
            noteId = NoteService.ingest_note(
                courseId=courseId,
                userId=userId,
                noteId=noteId,
                ingestType=ingestType,
                form=NoteForm.TEXT,
                rawText=rawText,
                title=noteName
            )

            if not noteId:
                return {'message': 'Note creation failed'}, 400

            logging.info(f"Source Node created successfully for text note")
            return {NOTEID: noteId}, 201
        except Exception as e:
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')
            logging.exception(f'Exception Stack trace: {e}')

create_text_file_note_parser = api.parser()
create_text_file_note_parser.add_argument('file', location='files', 
                        type=FileStorage, required=True,
                        help='The file to parse')
create_text_file_note_parser.add_argument('ingestType', location='form', 
                        type=str, required=True,
                        help='edit or create')
create_text_file_note_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the note')
create_text_file_note_parser.add_argument(NOTEID, location='form', 
                        type=str, required=False,
                        help='Optional note ID to edit')

        
@api.expect(create_text_file_note_parser)
@api.route('/create-text-file-note')
class TextFileIntake(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_text_file_note_parser.parse_args()
            courseId = args.get(COURSEID, None)
            noteId = args.get(NOTEID, None)
            file: FileStorage = args.get('file', None)
            ingestType = NoteService.ingest_to_enum(args.get('ingestType', None))
            userId = request.user_id

            valid, file_type = ValidationService.validate_text_file_inputs(
                file=file,
                courseId=courseId,
                userId=userId,
                ingestType=ingestType
                )
            
            if not valid:
                return {'message': 'Invalid inputs'}, 400
            
            print(f"noteId at start: {noteId}")

            noteId = NoteService.ingest_note(
                courseId=courseId,
                userId=userId,
                noteId=noteId,
                ingestType=ingestType,
                form=NoteForm.TEXT_FILE,
                file=file,
                file_type=file_type
                )
            
            if not noteId:
                return {'message': 'Note creation failed'}, 400

            logging.info(f"Source Node created successfully for source type: pdf and source: {file.filename}")
            return {NOTEID: noteId}, 201
        except Exception as e:
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')
            logging.exception(f'Exception Stack trace: {e}')