from werkzeug.datastructures import FileStorage
import logging
from .SupabaseService import SupabaseService
import threading

class NoteService:

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
                status='PENDING'
            )

            if len(note) == 0:
                return None

            noteId = note[0]['id']

            if form == 'audio':
                threading.Thread(target=NoteService._process_background_tasks, args=(noteId, audio_file)).start()


            logging.info(f"Note created successfully for courseId: {courseId}, userId: {userId}, form: {form}, audio_file: {audio_file}")

            return noteId
        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
            return None
        
    

    @staticmethod
    def _process_background_tasks(
        noteId: str,
        audio_file: FileStorage
        ):
        try:
            fileId = SupabaseService.upload_file(audio_file, noteId, 'audio-files')
            if fileId is None:
                logging.exception(f"Failed to upload file for note {noteId}")
                return
            else:
                logging.info(f"File uploaded successfully for note {noteId}")

        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
