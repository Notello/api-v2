import logging

from werkzeug.datastructures import FileStorage
from mutagen.mp3 import MP3
from mutagen.wave import WAVE

from flask_app.services.HelperService import HelperService
from flask_app.services.RatelimitService import RatelimitService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.AuthService import AuthService
from flask_app.services.NoteService import IngestType

from flask_app.constants import NOTE

class ValidationService:
    YOUTUBE_MAX_DURATION = 2 * 60 * 60  # 2 hours in seconds

    MAX_AUDIO_SIZE = 100 * 1024 * 1024   # 100MB in bytes

    MAX_TEXT_LENGTH = 5 * 1024 * 1024  # Approximately 5MB worth of text

    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes


    @staticmethod
    def invalid_ids(
        courseId: str,
        userId: str,
        reqUserId: str,
    ):
        return not HelperService.validate_all_uuid4(courseId, userId, reqUserId) \
        or not SupabaseService.param_id_exists(param='courseId', id=courseId) \
            or not SupabaseService.param_id_exists(param='userId', id=userId)
    
    @staticmethod
    def validate_ingest_type(
        ingestType: str
    ):
        return ingestType == IngestType.EDIT or ingestType == IngestType.CREATE
    
    @staticmethod
    def validate_common_inputs(
        courseId: str,
        userId: str,
        reqUserId: str,
        ingestType: str
    ):
        if ValidationService.invalid_ids(courseId, userId, reqUserId):
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return False
        
        if not AuthService.is_authed_for_userId(reqUserId=reqUserId, user_id_to_auth=userId):
            logging.error(f"User {userId} is not authorized for user {reqUserId}")
            return False
        
        if RatelimitService.is_rate_limited(userId=reqUserId, type=NOTE):
            logging.error(f"User {reqUserId} has exceeded their note upload rate limit")
            return False
        
        if not ValidationService.validate_ingest_type(ingestType):
            logging.error(f"Invalid ingest type: {ingestType}")
            return False
        
        return True

    @staticmethod
    def validate_youtube_inputs(
        youtubeUrl: str,
        courseId: str,
        userId: str,
        reqUserId: str,
        ingestType: str
    ):
        if not ValidationService.validate_common_inputs(courseId, userId, reqUserId, ingestType):
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return False
        
        duration = HelperService.get_video_duration(youtube_url=youtubeUrl)
        if not AuthService.is_super_admin(reqUserId) and duration > ValidationService.YOUTUBE_MAX_DURATION:
            logging.error(f"YouTube video exceeds the maximum duration of 2 hours: {youtubeUrl}")
            return False
        
        return True
    
    @staticmethod
    def validate_audio_inputs(
        audio_file: FileStorage,
        courseId: str,
        reqUserId: str,
        userId: str,
        ingestType: str
    ):
        if not ValidationService.validate_common_inputs(courseId, userId, reqUserId, ingestType):
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return False
        
        # Check audio duration
        try:
            audio_file.seek(0, 2)  # Move to the end of the file
            file_size = audio_file.tell()  # Get the size of the file
            audio_file.seek(0)  # Reset file pointer to the beginning

            if not AuthService.is_super_admin(reqUserId) and file_size > ValidationService.MAX_AUDIO_SIZE:
                logging.error(f"Audio file of size {file_size} exceeds the maximum file size of 5MB: {audio_file.filename}")
                return False
        except ValueError as e:
            return False
        
        return True
    
    @staticmethod
    def validate_text_inputs(
        rawText: str,
        noteName: str,
        courseId: str,
        reqUserId: str,
        userId: str,
        ingestType: str
    ):
        if not ValidationService.validate_common_inputs(courseId, userId, reqUserId, ingestType):
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return False
        
        # Check text length
        if not AuthService.is_super_admin(reqUserId) and len(rawText.encode('utf-8')) > ValidationService.MAX_TEXT_LENGTH:
            False
        
        return True
    
    @staticmethod
    def validate_text_file_inputs(
        file: FileStorage,
        courseId: str,
        reqUserId: str,
        userId: str,
        ingestType: str
    ):
        if not ValidationService.validate_common_inputs(courseId, userId, reqUserId, ingestType):
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return False, None
                    
        # Check file size
        file.seek(0, 2)  # Move to the end of the file
        file_size = file.tell()  # Get the size of the file
        file.seek(0)  # Reset file pointer to the beginning

        if not AuthService.is_super_admin(reqUserId) and file_size > ValidationService.MAX_FILE_SIZE:
            return False, None

        file_type = HelperService.guess_mime_type(file.filename)

        logging.info(f"File name: {file.filename}")
        logging.info(f"File type: {file_type}")

        if file_type is None:
            logging.exception(f"Failed to validate file")
            return False, None
        
        print(f"file at end: {type(file)}")
        
        return True, file_type