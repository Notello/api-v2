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
    YOUTUBE_MAX_DURATION = 5 * 60 * 60  # 2 hours in seconds

    MAX_AUDIO_SIZE = 100 * 1024 * 1024   # 100MB in bytes

    MAX_TEXT_LENGTH = 100 * 1024 * 1024  # Approximately 5MB worth of text

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 5MB in bytes


    @staticmethod
    def invalid_ids(
        courseId: str,
        userId: str
    ):
        return not HelperService.validate_all_uuid4(courseId, userId)
    
    @staticmethod
    def validate_ingest_type(
        ingestType: str
    ):
        return ingestType == IngestType.EDIT or ingestType == IngestType.CREATE
    
    @staticmethod
    def validate_common_inputs(
        courseId: str,
        userId: str,
        ingestType: str
    ):
        if ValidationService.invalid_ids(courseId, userId):
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return False, 400
        
        if RatelimitService.is_rate_limited(userId=userId, type=NOTE):
            logging.error(f"User {userId} has exceeded their note upload rate limit")
            return False, 250
        
        if not ValidationService.validate_ingest_type(ingestType):
            logging.error(f"Invalid ingest type: {ingestType}")
            return False, 400
        
        return True, 200

    @staticmethod
    def validate_youtube_inputs(
        youtubeUrl: str,
        courseId: str,
        userId: str,
        ingestType: str
    ):
        valid, code = ValidationService.validate_common_inputs(courseId, userId, ingestType)
        if not valid:
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return valid, code
        
        return True, 200
    
    @staticmethod
    def validate_audio_inputs(
        audio_file: FileStorage,
        courseId: str,
        userId: str,
        ingestType: str
    ):
        valid, code = ValidationService.validate_common_inputs(courseId, userId, ingestType)
        if not valid:
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return valid, code
        
        # Check audio duration
        try:
            audio_file.seek(0, 2)  # Move to the end of the file
            file_size = audio_file.tell()  # Get the size of the file
            audio_file.seek(0)  # Reset file pointer to the beginning

            if not AuthService.is_super_admin(userId) and file_size > ValidationService.MAX_AUDIO_SIZE:
                logging.error(f"Audio file of size {file_size} exceeds the maximum file size of 5MB: {audio_file.filename}")
                return False, 400
        except ValueError as e:
            return False, 400
        
        return True, 200
    
    @staticmethod
    def validate_text_inputs(
        rawText: str,
        noteName: str,
        courseId: str,
        userId: str,
        ingestType: str
    ):
        valid, code = ValidationService.validate_common_inputs(courseId, userId, ingestType)
        if not valid:
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return valid, code
        
        if len(rawText.encode('utf-8')) > ValidationService.MAX_TEXT_LENGTH and not AuthService.is_super_admin(userId):
            return False, 400
        
        return True, 200
    
    @staticmethod
    def validate_text_file_inputs(
        file: FileStorage,
        courseId: str,
        userId: str,
        ingestType: str
    ):
        valid, code = ValidationService.validate_common_inputs(courseId, userId, ingestType)
        if not valid:
            logging.error(f"Invalid userId: {userId}, courseId: {courseId}")
            return valid, code, None
                    
        # Check file size
        file.seek(0, 2)  # Move to the end of the file
        file_size = file.tell()  # Get the size of the file
        file.seek(0)  # Reset file pointer to the beginning

        if file_size > ValidationService.MAX_FILE_SIZE and not AuthService.is_super_admin(userId):
            return False, 400, None

        file_type = HelperService.guess_mime_type(file.filename)

        logging.info(f"File name: {file.filename}")
        logging.info(f"File type: {file_type}")

        if file_type is None or file_type == 'application/octet-stream':
            logging.exception(f"Failed to validate file")
            return False, 401, None
        
        print(f"file at end: {type(file)}")
        
        return True, 200, file_type