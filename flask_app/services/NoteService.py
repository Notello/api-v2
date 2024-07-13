from enum import Enum
from io import BytesIO
from werkzeug.datastructures import FileStorage
import logging
from .SupabaseService import SupabaseService
from .RunpodService import RunpodService
from .GraphCreationService import GraphCreationService
from flask_app.src.document_sources.pdf_loader import extract_text

class NoteForm(Enum):
    TEXT = 'text'
    AUDIO = 'audio'
    YOUTUBE = 'youtube'
    TEXT_FILE = 'text-file'

class NoteService:

    form_to_status = {
        NoteForm.AUDIO: 'pending',
        NoteForm.YOUTUBE: 'complete',
        NoteForm.TEXT: 'complete',
        NoteForm.TEXT_FILE: 'complete',
    }

    @staticmethod
    def create_note(
        courseId: str,
        userId: str,
        form: NoteForm,
        sourceUrl: str = '',
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

            logging.info(f"Note created successfully for courseId: {courseId}, userId: {userId}, form: {form}")

            return noteId
        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
            return None


    @staticmethod
    def audio_file_to_graph(
        noteId: str,
        courseId: str,
        userId: str,
        audio_file: FileStorage,
        keywords: str
        ):
        try:
            file_content = audio_file.read()
            fileId = SupabaseService.upload_file(
                file=file_content, 
                fileName=noteId,
                bucketName='audio-files',
                contentType='audio/*'
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
            
            GraphCreationService.create_graph_from_raw_text(
                rawText=output,
                noteId=noteId, 
                courseId=courseId, 
                userId=userId,
                fileName=audio_file.filename
                )
            
            logging.info(f"File uploaded successfully for note {noteId}")

        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')


    @staticmethod
    def pdf_file_to_graph(
        noteId: str,
        courseId: str,
        userId: str,
        file_name: str,
        file_content: BytesIO,
        file_type: str
        ):
        try:
            output = extract_text(file_content, file_name, file_type)

            if output is None:
                logging.exception(f"Failed to transcribe file for note {noteId}")
                return

            fileId = SupabaseService.upload_file(
                file=file_content, 
                fileName=noteId, 
                bucketName='pdf-files',
                contentType='application/pdf'
                )

            if fileId is None:
                logging.exception(f"Failed to upload file for note {noteId}")
                return
                        
            GraphCreationService.create_graph_from_raw_text(
                rawText=output,
                noteId=noteId, 
                courseId=courseId, 
                userId=userId,
                fileName=file_name
                )
            
            logging.info(f"File uploaded successfully for note {noteId}")

        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
