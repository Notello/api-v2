from datetime import datetime
import logging
from flask_restx import Namespace, Resource
from werkzeug.datastructures import FileStorage

from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.NoteService import NoteForm, NoteService
from flask_app.services.GraphCreationService import GraphCreationService
from flask_app.services.HelperService import HelperService
from flask_app.constants import COURSEID, NOTEID, USERID


api = Namespace('upload')

intake_youtube_parser = api.parser()
intake_youtube_parser.add_argument('youtubeUrl', location='form',
                        type=str, required=False,
                        help='Youtube url')
intake_youtube_parser.add_argument(USERID, location='form',
                        type=str, required=True,
                        help='Supabase id of the user')
intake_youtube_parser.add_argument(COURSEID, location='form',
                        type=str, required=True,
                        help='Id of the course to add the note to')

@api.expect(intake_youtube_parser)
@api.route('/intake-youtube')
class YoutubeIntake(Resource):
    def post(self):
        try:
            logging.info('In youtube intake post')

            args = intake_youtube_parser.parse_args()
            youtubeUrl = args.get('youtubeUrl', None)
            userId = args.get(USERID, None)
            courseId = args.get(COURSEID, None)

            logging.info(f"Youtube url: {youtubeUrl}")

            if not HelperService.validate_all_uuid4(courseId, userId):
                return {'message': 'Invalid courseId or userId'}, 400
            
            title = HelperService.get_youtube_title(youtube_url=youtubeUrl)
            
            noteId = NoteService.create_note(
                courseId=courseId, 
                userId=userId, 
                form=NoteForm.YOUTUBE,
                sourceUrl=youtubeUrl, 
                title=title
                )
        
            if not HelperService.validate_all_uuid4(noteId):
                return {'message': 'Note creation failed'}, 400

            ContextAwareThread(
                target=NoteService.youtube_video_to_graph,
                args=(noteId, courseId, userId, youtubeUrl, title)
            ).start()

            logging.info(f"Source Node created successfully for source type: youtube and source: {youtubeUrl}")

            return {NOTEID: noteId}, 200
        except Exception as e:
            message = f" Unable to create source node for source type: youtube, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400
        
create_audio_note_parser = api.parser()
create_audio_note_parser.add_argument('file', location='files',
                        type=FileStorage, required=True,
                        help='Audio file to be transcribed')
create_audio_note_parser.add_argument('keywords', location='form', 
                        type=str, required=False,
                        help='Space-separated keywords to enhance transcription accuracy')
create_audio_note_parser.add_argument(USERID, location='form', 
                        type=str, required=True,
                        help='Supabase ID of the user')
create_audio_note_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the note')

@api.expect(create_audio_note_parser)
@api.route('/create-audio-note')
class AudioIntake(Resource):
    def post(self):
        try:
            args = create_audio_note_parser.parse_args()
            userId = args.get(USERID, None)
            courseId = args.get(COURSEID, None)
            audio_file = args.get('file', None)
            keywords = args.get('keywords', None)

            if not HelperService.validate_all_uuid4(courseId, userId):
                return {'message': 'Invalid courseId or userId'}, 400

            noteId = NoteService.create_note(
                courseId=courseId,
                userId=userId,
                form=NoteForm.AUDIO,
                title=f"Audio File: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if not HelperService.validate_all_uuid4(noteId):
                return {'message': 'Note creation failed'}, 400

            ContextAwareThread(
                    target=NoteService.audio_file_to_graph,
                    args=(noteId, courseId, userId, audio_file, keywords)
            ).start()
            
            logging.info(f"Source Node created successfully for source type: audio and source: {audio_file}")
            return {NOTEID: noteId}, 201
        except Exception as e:
            message = f" Unable to create source node for source type: audio and source: {audio_file}, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400
        
create_text_note_parser = api.parser()
create_text_note_parser.add_argument('rawText', location='form', 
                        type=str, required=True,
                        help='The raw text to ingest')
create_text_note_parser.add_argument('noteName', location='form', 
                        type=str, required=True,
                        help='The name of the note')
create_text_note_parser.add_argument(USERID, location='form', 
                        type=str, required=True,
                        help='Supabase ID of the user')
create_text_note_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the note')

@api.expect(create_text_note_parser)
@api.route('/create-text-note')
class TextIntake(Resource):
    def post(self):
        args = create_text_note_parser.parse_args()
        userId = args.get(USERID, None)
        courseId = args.get(COURSEID, None)
        rawText = args.get('rawText', None)
        noteName = args.get('noteName', None)

        if not HelperService.validate_all_uuid4(courseId, userId):
            return {'message': 'Invalid courseId or userId'}, 400

        noteId = NoteService.create_note(
            courseId=courseId,
            userId=userId,
            form=NoteForm.TEXT,
            rawText=rawText,
            title=noteName
        )

        if not HelperService.validate_all_uuid4(noteId):
            return {'message': 'Note creation failed'}, 400

        ContextAwareThread(
                target=GraphCreationService.create_graph_from_raw_text,
                args=(noteId, courseId, userId, rawText, noteName)
        ).start()

        logging.info(f"Source Node created successfully for source type: text and source: {rawText}")
        return {NOTEID: noteId}, 201

create_text_file_note_parser = api.parser()
create_text_file_note_parser.add_argument('file', location='files', 
                        type=FileStorage, required=True,
                        help='The file to parse')
create_text_file_note_parser.add_argument(USERID, location='form', 
                        type=str, required=True,
                        help='Supabase ID of the user')
create_text_file_note_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the note')
        
@api.expect(create_text_file_note_parser)
@api.route('/create-text-file-note')
class TextFileIntake(Resource):
    def post(self):
        args = create_text_file_note_parser.parse_args()
        userId = args.get(USERID, None)
        courseId = args.get(COURSEID, None)
        file: FileStorage = args.get('file', None)

        if not HelperService.validate_all_uuid4(courseId, userId):
            return {'message': 'Invalid courseId or userId'}, 400
        
        file_type = HelperService.guess_mime_type(file.filename)

        logging.info(f"File content: {file.filename}")
        logging.info(f"File type: {file_type}")

        if file_type is None:
            logging.exception(f"Failed to transcribe file for note {noteId}")
            return {'message': 'Invalid file type'}, 400

        noteId = NoteService.create_note(
            courseId=courseId,
            userId=userId,
            form=NoteForm.TEXT_FILE,
            title=file.filename
        )

        if not HelperService.validate_all_uuid4(noteId):
            return {'message': 'Note creation failed'}, 400
        
        file_content = file.read()

        ContextAwareThread(
                target=NoteService.pdf_file_to_graph,
                args=(noteId, courseId, userId, file.filename, file_content, file_type)
        ).start()

        logging.info(f"Source Node created successfully for source type: pdf and source: {file.filename}")
        return {NOTEID: noteId}, 201