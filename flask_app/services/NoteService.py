from werkzeug.datastructures import FileStorage
import logging
from .SupabaseService import SupabaseService
from .RunpodService import RunpodService


class NoteService:

    form_to_status = {
        'audio': 'pending',
        'youtube': 'complete'
    }

    @staticmethod
    def create_note(
        courseId: str,
        userId: str,
        form: str,
        audio_file: FileStorage = None,
        sourceUrl: str = '',
        keywords: str = ''
    ):
        try:          
            note = SupabaseService.add_note(
                courseId=courseId,
                userId=userId,
                form=form,
                content='',
                sourceUrl=sourceUrl,
                status=NoteService.form_to_status[form]
            )

            if len(note) == 0:
                return None

            noteId = note[0]['id']

            logging.info(f"Note created successfully for courseId: {courseId}, userId: {userId}, form: {form}, audio_file: {audio_file}")

            return noteId
        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
            return None
        
    

    @staticmethod
    def upload_and_transcribe(
        noteId: str,
        audio_file: FileStorage,
        keywords: str
        ):
        try:
            fileId = SupabaseService.upload_file(audio_file, noteId, 'audio-files')
            if fileId is None:
                logging.exception(f"Failed to upload file for note {noteId}")
                return

            output = RunpodService.transcribe(noteId, keywords)
            
            if output is None:
                logging.exception(f"Failed to transcribe file for note {noteId}")
                return
            
            logging.info(f"File uploaded successfully for note {noteId}")

        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
