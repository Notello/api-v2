from enum import Enum
from io import BytesIO
from werkzeug.datastructures import FileStorage
import logging
from datetime import datetime

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.RunpodService import RunpodService
from flask_app.services.GraphCreationService import GraphCreationService
from flask_app.services.SimilarityService import SimilarityService
from flask_app.services.TimestampService import TimestampService
from flask_app.services.HelperService import HelperService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.AuthService import AuthService
from flask_app.services.GraphDeletionService import GraphDeletionService

from flask_app.src.document_sources.pdf_loader import extract_text
from flask_app.constants import NOTE, NOTEID

class NoteForm(Enum):
    TEXT = 'text'
    AUDIO = 'audio'
    YOUTUBE = 'youtube'
    TEXT_FILE = 'text-file'

class IngestType(Enum):
    EDIT = 'edit'
    CREATE = 'create'

class NoteService:

    form_to_status = {
        NoteForm.AUDIO: 'pending',
        NoteForm.YOUTUBE: 'pending',
        NoteForm.TEXT: 'complete',
        NoteForm.TEXT_FILE: 'complete',
    }

    @staticmethod
    def form_to_bucket(form: str):
        if form == "audio":
            return 'audio-files'
        elif form == "text-file":
            return 'pdf-files'
        else:
            return None

    @staticmethod
    def ingest_to_enum(ingestType: str):
        if ingestType == 'edit':
            logging.info(f"ingestType: {ingestType}")
            logging.info(f"IngestType.EDIT: {IngestType.EDIT}")
            return IngestType.EDIT
        elif ingestType == 'create':
            logging.info(f"ingestType: {ingestType}")
            logging.info(f"IngestType.CREATE: {IngestType.CREATE}")
            return IngestType.CREATE

        return None
    
    @staticmethod
    def delete_note(noteId: str):
        if not HelperService.validate_all_uuid4(noteId):
            logging.error(f'Invalid noteId: {noteId}')
            return None
        
        noteType = SupabaseService.get_note_type(noteId)
        bucketName = NoteService.form_to_bucket(noteType)

        SupabaseService.delete_note(noteId=noteId, bucketName=bucketName)
        GraphDeletionService.delete_node_for_param(param=NOTEID, id=noteId)

    @staticmethod
    def create_note(
        courseId: str,
        userId: str,
        noteId: str,
        form: NoteForm,
        sourceUrl: str = '',
        rawText: str = '',
        title: str = ''
    ):
        try:          
            print(f"noteId at create: {noteId}")    
            note = SupabaseService.add_note(
                courseId=courseId,
                userId=userId,
                form=form.value,
                content=rawText,
                sourceUrl=sourceUrl,
                status=NoteService.form_to_status[form],
                title=title,
                noteId=noteId
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
    def ingest_note(
        courseId: str,
        userId: str,
        form: NoteForm,
        ingestType: IngestType,
        sourceUrl: str = '',
        rawText: str = '',
        title: str = '',
        file_type: str = '',
        file: FileStorage = None,
        noteId: str = None
    ):
        if ingestType == IngestType.EDIT:
            if form == NoteForm.YOUTUBE:
                return NoteService.edit_youtube_note(
                    courseId=courseId,
                    userId=userId,
                    youtubeUrl=sourceUrl,
                    noteId=noteId
                    )
            elif form == NoteForm.AUDIO:
                return NoteService.edit_audio_note(
                    courseId=courseId,
                    userId=userId,
                    audio_file=file,
                    noteId=noteId
                    )
            elif form == NoteForm.TEXT:
                return NoteService.edit_text_note(
                    courseId=courseId,
                    userId=userId,
                    rawText=rawText,
                    noteName=title,
                    noteId=noteId
                    )
            elif form == NoteForm.TEXT_FILE:
                return NoteService.edit_text_file_note(
                    courseId=courseId,
                    userId=userId,
                    file=file,
                    file_type=file_type,
                    noteId=noteId
                    )
        elif ingestType == IngestType.CREATE:
            if form == NoteForm.YOUTUBE:
                return NoteService.create_youtube_note(
                    courseId=courseId,
                    userId=userId,
                    youtubeUrl=sourceUrl,
                    )
            elif form == NoteForm.AUDIO:
                return NoteService.create_audio_note(
                    courseId=courseId,
                    userId=userId,
                    audio_file=file,
                    )
            elif form == NoteForm.TEXT:
                return NoteService.create_text_note(
                    courseId=courseId,
                    userId=userId,
                    rawText=rawText,
                    noteName=title,
                    )
            elif form == NoteForm.TEXT_FILE:
                return NoteService.create_text_file_note(
                    courseId=courseId,
                    userId=userId,
                    file=file,
                    file_type=file_type,
                    )
     
        
    @staticmethod
    def edit_youtube_note(
        courseId: str,
        userId: str,
        youtubeUrl: str,
        noteId: str
    ):
        logging.info(f"Editing youtube note: {youtubeUrl}")
        if not AuthService.can_edit_note(userId, noteId):
            logging.error(f"User {userId} is not authorized to edit note {noteId}")
            return False
        
        NoteService.delete_note(noteId)
        GraphDeletionService.delete_node_for_param(NOTEID, noteId)

        return NoteService.create_youtube_note(
            courseId=courseId,
            userId=userId,
            youtubeUrl=youtubeUrl,
            origionalNoteId=noteId
            )

    @staticmethod
    def create_youtube_note(
        courseId: str,
        userId: str,
        youtubeUrl: str,
        origionalNoteId: str = None
    ): 
        logging.info(f"Creating youtube note: {youtubeUrl}")
        noteId = NoteService.create_note(
            courseId=courseId, 
            userId=userId, 
            form=NoteForm.YOUTUBE,
            sourceUrl=youtubeUrl, 
            title="Youtube Video",
            noteId=origionalNoteId
            )
    
        if not HelperService.validate_all_uuid4(noteId):
            return None

        ContextAwareThread(
            target=NoteService.youtube_video_to_graph,
            args=(noteId, courseId, userId, youtubeUrl)
        ).start()

        return noteId
    
    @staticmethod
    def edit_audio_note(
        courseId: str,
        userId: str,
        audio_file: FileStorage,
        noteId: str
    ):
        logging.info(f"Editing audio note: {audio_file}")
        if not AuthService.can_edit_note(userId, noteId):
            logging.error(f"User {userId} is not authorized to edit note {noteId}")
            return False

        NoteService.delete_note(noteId)
        GraphDeletionService.delete_node_for_param(NOTEID, noteId)

        return NoteService.create_audio_note(
            courseId=courseId,
            userId=userId,
            audio_file=audio_file,
            origionalNoteId=noteId
            )
    
    @staticmethod
    def create_audio_note(
        courseId: str,
        userId: str,
        audio_file: FileStorage,
        origionalNoteId: str = None
    ):
        logging.info(f"Creating audio note: {audio_file}")
        noteId = NoteService.create_note(
            courseId=courseId,
            userId=userId,
            form=NoteForm.AUDIO,
            title=f"Audio File: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            noteId=origionalNoteId
        )

        if not HelperService.validate_all_uuid4(noteId):
            return None
        
        ContextAwareThread(
                target=NoteService.audio_file_to_graph,
                args=(noteId, courseId, userId, audio_file)
        ).start()

        return noteId
    
    @staticmethod
    def edit_text_note(
        courseId: str,
        userId: str,
        rawText: str,
        noteName: str,
        noteId: str
    ):
        logging.info(f"Editing text note: {noteName}")
        if not AuthService.can_edit_note(userId, noteId):
            logging.error(f"User {userId} is not authorized to edit note {noteId}")
            return False

        NoteService.delete_note(noteId)
        GraphDeletionService.delete_node_for_param(NOTEID, noteId)

        return NoteService.create_text_note(
            courseId=courseId,
            userId=userId,
            rawText=rawText,
            noteName=noteName,
            origionalNoteId=noteId
            )
    
    @staticmethod
    def create_text_note(
        courseId: str,
        userId: str,
        rawText: str,
        noteName: str,
        origionalNoteId: str = None
    ):
        noteId = NoteService.create_note(
            courseId=courseId,
            userId=userId,
            form=NoteForm.TEXT,
            rawText=rawText,
            title=noteName,
            noteId=origionalNoteId
        )

        if not HelperService.validate_all_uuid4(noteId):
            return None
        
        ContextAwareThread(
                target=GraphCreationService.create_graph_from_raw_text,
                args=(noteId, courseId, userId, rawText, noteName)
        ).start()

        return noteId
    
    @staticmethod
    def edit_text_file_note(
        courseId: str,
        userId: str,
        file: FileStorage,
        file_type: str,
        noteId: str
    ):
        logging.info(f"Editing text file note: {type(file)}")
        if not AuthService.can_edit_note(userId, noteId):
            logging.error(f"User {userId} is not authorized to edit note {noteId}")
            return False

        NoteService.delete_note(noteId)
        GraphDeletionService.delete_node_for_param(NOTEID, noteId)

        print(f"noteId at edit: {noteId}")

        return NoteService.create_text_file_note(
            courseId=courseId,
            userId=userId,
            file=file,
            file_type=file_type,
            origionalNoteId=noteId
            )
    
    @staticmethod
    def create_text_file_note(
        courseId: str,
        userId: str,
        file_type: str,
        file: FileStorage = None,
        origionalNoteId: str = None
    ):
        print(f"file at sSHSHSHStart: {type(file)}")

        noteId = NoteService.create_note(
            courseId=courseId,
            userId=userId,
            form=NoteForm.TEXT_FILE,
            title=file.filename,
            noteId=origionalNoteId
        )

        if not HelperService.validate_all_uuid4(noteId):
            return None
        
        file_content = file.read()

        ContextAwareThread(
                target=NoteService.pdf_file_to_graph,
                args=(noteId, courseId, userId, file.filename, file_content, file_type)
        ).start()

        return noteId
        
    @staticmethod
    def youtube_video_to_graph(
        noteId: str,
        courseId: str,
        userId: str,
        youtubeUrl: str,
    ):
        title = HelperService.get_youtube_title(youtube_url=youtubeUrl)

        SupabaseService.update_note(noteId=noteId, key='title', value=title)

        logging.info(f"Creating youtube note: {youtubeUrl}")
        try:
            similar = SimilarityService.check_youtube_similarity(
                courseId=courseId,
                noteId=noteId,
                sourceUrl=youtubeUrl
                )

            if similar:
                logging.info(f"Youtube video similar to existing note: {youtubeUrl}")
                return None
                
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
        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')

    @staticmethod
    def audio_file_to_graph(
        noteId: str,
        courseId: str,
        userId: str,
        audio_file: FileStorage,
        ):
        logging.info(f"Creating audio note: {audio_file}")

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
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')
            logging.exception(f'Exception Stack trace: {e}')


    @staticmethod
    def pdf_file_to_graph(
        noteId: str,
        courseId: str,
        userId: str,
        file_name: str,
        file_content: BytesIO,
        file_type: str,
        ):

        logging.info(f"Creating text file note: {file_name}")
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
                fileName=file_name,
                )
            
            logging.info(f"File uploaded successfully for note {noteId}")

        except Exception as e:
            SupabaseService.update_note(noteId=noteId, key='contentStatus', value='error')
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')
            logging.exception(f'Exception Stack trace: {e}')
