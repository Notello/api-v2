from enum import Enum
from werkzeug.datastructures import FileStorage
import logging
from .SupabaseService import SupabaseService
from .RunpodService import RunpodService
from .GraphService import GraphService

class NoteForm(Enum):
    TEXT = 'text'
    AUDIO = 'audio'
    YOUTUBE = 'youtube'

class NoteService:

    form_to_status = {
        NoteForm.AUDIO: 'pending',
        NoteForm.YOUTUBE: 'complete',
        NoteForm.TEXT: 'complete',
    }

    @staticmethod
    def create_note(
        courseId: str,
        userId: str,
        form: NoteForm,
        audio_file: FileStorage = None,
        sourceUrl: str = '',
        keywords: str = '',
        rawText: str = ''
    ):
        try:          
            note = SupabaseService.add_note(
                courseId=courseId,
                userId=userId,
                form=form.value,
                content=rawText,
                sourceUrl=sourceUrl,
                status=NoteService.form_to_status[form],
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
    def audio_file_to_graph(
        courseId: str,
        userId: str,
        noteId: str,
        audio_file: FileStorage,
        keywords: str
        ):
        try:
            fileId = SupabaseService.upload_file(
                file=audio_file, 
                fileName=noteId, 
                bucketName='audio-files'
                )

            if fileId is None:
                logging.exception(f"Failed to upload file for note {noteId}")
                return

            output = RunpodService.transcribe(
                fileName=noteId, 
                keywords=keywords
                )

            if output is None:
                logging.exception(f"Failed to transcribe file for note {noteId}")
                return
            
            out = GraphService.create_graph_from_raw_text(
                rawText=output,
                noteId=noteId, 
                courseId=courseId, 
                userId=userId,
                fileName=audio_file.filename
                )
            
            logging.info(f"File uploaded successfully for note {noteId}")

        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
