from datetime import datetime
import logging
from flask_restx import Namespace, Resource
from werkzeug.datastructures import FileStorage
from mutagen.mp3 import MP3
from mutagen.wave import WAVE

from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.NoteService import NoteForm, NoteService
from flask_app.services.GraphCreationService import GraphCreationService
from flask_app.services.HelperService import HelperService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.AuthService import AuthService
from flask_app.services.RatelimitService import RatelimitService


from flask_app.constants import COURSEID, NOTE, NOTEID, USERID
from flask_app.routes.middleware import token_required

from flask import g



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
    MAX_DURATION = 2 * 60 * 60  # 2 hours in seconds

    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            logging.info('In youtube intake post')

            args = intake_youtube_parser.parse_args()
            youtubeUrl = args.get('youtubeUrl', None)
            userId = args.get(USERID, None)
            courseId = args.get(COURSEID, None)
            reqUserId = g.user_id

            logging.info(f"Youtube url: {youtubeUrl}")

            if not HelperService.validate_all_uuid4(courseId, userId, reqUserId) \
            or not SupabaseService.param_id_exists(param='courseId', id=courseId) \
                or not SupabaseService.param_id_exists(param='userId', id=userId):
                logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
                return {'message': 'Invalid courseId or userId'}, 400
            
            if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=userId):
                logging.error(f"User {userId} is not authorized to create a summary for user {reqUserId}")
                return {'message': 'You do not have permission to create a summary for this user'}, 400
            
            if RatelimitService.is_rate_limited(userId, NOTE):
                logging.error(f"User {reqUserId} has exceeded their note upload rate limit")
                return {'message': 'You have exceeded your note upload rate limit'}, 400
            
            duration = HelperService.get_video_duration(youtube_url=youtubeUrl)
            title = HelperService.get_youtube_title(youtube_url=youtubeUrl)
            if duration > self.MAX_DURATION:
                logging.error(f"YouTube video exceeds the maximum duration of 2 hours: {youtubeUrl}")
                return {'message': 'YouTube video exceeds the maximum duration of 2 hours'}, 400

            noteId = NoteService.create_note(
                courseId=courseId, 
                userId=userId, 
                form=NoteForm.YOUTUBE,
                sourceUrl=youtubeUrl, 
                title=title if title is not None else "Youtube Video"
                )
        
            if not HelperService.validate_all_uuid4(noteId):
                RatelimitService.remove_rate_limit(rateLimitId)
                return {'message': 'Note creation failed'}, 400

            rateLimitId = RatelimitService.add_rate_limit(userId, NOTE, 1)

            ContextAwareThread(
                target=NoteService.youtube_video_to_graph,
                args=(noteId, courseId, userId, youtubeUrl, title, rateLimitId)
            ).start()

            logging.info(f"Source Node created successfully for source type: youtube and source: {youtubeUrl}")

            return {NOTEID: noteId}, 200
        except Exception as e:
            message = f"Unable to create source node for source type: youtube, Exception: {e}"
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
    MAX_DURATION = 2 * 60 * 60  # 2 hours in seconds

    def get_audio_length(self, file):
        file.seek(0)  # Ensure we're at the start of the file
        try:
            # Try MP3 first
            audio = MP3(file)
            return audio.info.length
        except:
            file.seek(0)  # Reset file pointer
            try:
                # Try WAV
                audio = WAVE(file)
                return audio.info.length
            except:
                # Add more audio formats here as needed
                logging.error(f"Unsupported audio format: {file.filename}")
                raise ValueError("Unsupported audio format")

    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_audio_note_parser.parse_args()
            userId = args.get(USERID, None)
            courseId = args.get(COURSEID, None)
            audio_file = args.get('file', None)
            keywords = args.get('keywords', None)
            reqUserId = g.user_id

            if not HelperService.validate_all_uuid4(courseId, userId, reqUserId) \
            or not SupabaseService.param_id_exists(param='courseId', id=courseId) \
                or not SupabaseService.param_id_exists(param='userId', id=userId):
                return {'message': 'Invalid courseId or userId'}, 400
            
            if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=userId):
                logging.error(f"User {userId} is not authorized to create a note for user {reqUserId}")
                return {'message': 'You do not have permission to create a note for this user'}, 400
            
            if RatelimitService.is_rate_limited(userId, NOTE):
                logging.error(f"User {reqUserId} has exceeded their note upload rate limit")
                return {'message': 'You have exceeded your note upload rate limit'}, 400
            
            # Check audio duration
            try:
                duration = self.get_audio_length(audio_file)
                if duration > self.MAX_DURATION:
                    return {'message': 'Audio file exceeds the maximum duration of 2 hours'}, 400
            except ValueError as e:
                return {'message': str(e)}, 400

            noteId = NoteService.create_note(
                courseId=courseId,
                userId=userId,
                form=NoteForm.AUDIO,
                title=f"Audio File: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if not HelperService.validate_all_uuid4(noteId):
                return {'message': 'Note creation failed'}, 400
            
            rateLimitId = RatelimitService.add_rate_limit(userId, NOTE, 1)

            ContextAwareThread(
                    target=NoteService.audio_file_to_graph,
                    args=(noteId, courseId, userId, audio_file, keywords, rateLimitId)
            ).start()
            
            logging.info(f"Source Node created successfully for source type: audio and source: {audio_file}")
            return {NOTEID: noteId}, 201
        except Exception as e:
            message = f"Unable to create source node for source type: audio and source: {audio_file}, Exception: {e}"
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
    MAX_TEXT_LENGTH = 5 * 1024 * 1024  # Approximately 5MB worth of text

    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_text_note_parser.parse_args()
            userId = args.get(USERID, None)
            courseId = args.get(COURSEID, None)
            rawText = args.get('rawText', None)
            noteName = args.get('noteName', None)
            reqUserId = g.user_id

            if not HelperService.validate_all_uuid4(courseId, userId, reqUserId) \
                or not SupabaseService.param_id_exists(param='courseId', id=courseId) \
                    or not SupabaseService.param_id_exists(param='userId', id=userId):
                return {'message': 'Invalid courseId or userId'}, 400
            
            if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=userId):
                logging.error(f"User {userId} is not authorized to create a note for user {reqUserId}")
                return {'message': 'You do not have permission to create a note for this user'}, 400
            
            if RatelimitService.is_rate_limited(userId, NOTE):
                logging.error(f"User {userId} is rate limited for note creation")
                return {'message': 'You have exceeded your note creation rate limit'}, 400
            
            # Check text length
            if len(rawText.encode('utf-8')) > self.MAX_TEXT_LENGTH:
                RatelimitService.remove_rate_limit(rateLimitId)
                return {'message': 'Text size exceeds the maximum limit of approximately 5MB'}, 400

            noteId = NoteService.create_note(
                courseId=courseId,
                userId=userId,
                form=NoteForm.TEXT,
                rawText=rawText,
                title=noteName
            )

            if not HelperService.validate_all_uuid4(noteId):
                return {'message': 'Note creation failed'}, 400
            
            rateLimitId = RatelimitService.add_rate_limit(userId, NOTE, 1)

            ContextAwareThread(
                    target=GraphCreationService.create_graph_from_raw_text,
                    args=(noteId, courseId, userId, rawText, noteName, rateLimitId)
            ).start()

            logging.info(f"Source Node created successfully for source type: text and source: {rawText}")
            return {NOTEID: noteId}, 201
        except Exception as e:
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')
            logging.exception(f'Exception Stack trace: {e}')

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
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_text_file_note_parser.parse_args()
            userId = args.get(USERID, None)
            courseId = args.get(COURSEID, None)
            file: FileStorage = args.get('file', None)
            reqUserId = g.user_id

            if not HelperService.validate_all_uuid4(courseId, userId, reqUserId) \
                or not SupabaseService.param_id_exists(param='courseId', id=courseId) \
                    or not SupabaseService.param_id_exists(param='userId', id=userId):
                return {'message': 'Invalid courseId or userId'}, 400
            
            if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=userId):
                logging.error(f"User {userId} is not authorized to create a note for user {reqUserId}")
                return {'message': 'You do not have permission to create a note for this user'}, 400
            
            if RatelimitService.is_rate_limited(userId, NOTE):
                logging.error(f"User {userId} is rate limited for note creation")
                return {'message': 'You have exceeded your note creation rate limit'}, 400
                        
            # Check file size
            file.seek(0, 2)  # Move to the end of the file
            file_size = file.tell()  # Get the size of the file
            file.seek(0)  # Reset file pointer to the beginning

            if file_size > self.MAX_FILE_SIZE:
                return {'message': 'File size exceeds the maximum limit of 5MB'}, 400

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

            rateLimitId = RatelimitService.add_rate_limit(userId, NOTE, 1)

            ContextAwareThread(
                    target=NoteService.pdf_file_to_graph,
                    args=(noteId, courseId, userId, file.filename, file_content, file_type, rateLimitId)
            ).start()

            logging.info(f"Source Node created successfully for source type: pdf and source: {file.filename}")
            return {NOTEID: noteId}, 201
        except Exception as e:
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')
            logging.exception(f'Exception Stack trace: {e}')