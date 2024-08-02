from enum import Enum
from io import BytesIO
from werkzeug.datastructures import FileStorage
import logging
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.RunpodService import RunpodService
from flask_app.services.GraphCreationService import GraphCreationService
from flask_app.services.SimilarityService import SimilarityService
from flask_app.services.TimestampService import TimestampService
from flask_app.services.HelperService import HelperService
from flask_app.src.document_sources.pdf_loader import extract_text

class NoteForm(Enum):
    TEXT = 'text'
    AUDIO = 'audio'
    YOUTUBE = 'youtube'
    TEXT_FILE = 'text-file'

class NoteService:

    form_to_status = {
        NoteForm.AUDIO: 'pending',
        NoteForm.YOUTUBE: 'pending',
        NoteForm.TEXT: 'complete',
        NoteForm.TEXT_FILE: 'complete',
    }

    @staticmethod
    def create_note(
        courseId: str,
        userId: str,
        form: NoteForm,
        sourceUrl: str = '',
        rawText: str = '',
        title: str = ''
    ):
        try:          
            note = SupabaseService.add_note(
                courseId=courseId,
                userId=userId,
                form=form.value,
                content=rawText,
                sourceUrl=sourceUrl,
                status=NoteService.form_to_status[form],
                title=title
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
    def youtube_video_to_graph(
        noteId: str,
        courseId: str,
        userId: str,
        youtubeUrl: str,
        title: str,
    ):
        similar = SimilarityService.check_youtube_similarity(
            courseId=courseId,
            noteId=noteId,
            sourceUrl=youtubeUrl
            )

        if similar:
            return
            
        timestamps = TimestampService.get_youtube_timestamps(youtube_url=youtubeUrl)

        SupabaseService.update_note(noteId=noteId, key='sourceUrl', value=youtubeUrl)
        SupabaseService.update_note(noteId=noteId, key='contentStatus', value='complete')

        GraphCreationService.create_graph_from_timestamps(
            timestamps=timestamps,
            import_type='youtube',
            document_name=title,
            noteId=noteId,
            courseId=courseId,
            userId=userId
            )

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

            if output is None or 'data' not in output:
                logging.exception(f"Failed to transcribe file for note {noteId}")
                return
            
            GraphCreationService.create_graph_from_timestamps(
                timestamps=output['data'],
                import_type='audio',
                document_name=audio_file.filename,
                noteId=noteId,
                courseId=courseId,
                userId=userId
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
