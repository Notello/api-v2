from .SupabaseService import SupabaseService
import threading

class NoteService:

    @staticmethod
    def create_audio_note(
        courseId, 
        userId, 
        form, 
        audio_file, 
        keywords
    ):
        try:
            note = SupabaseService.add_note(
                courseId=courseId,
                userId=userId,
                form=form,
                content='',
                status='PENDING'
            )

            if len(note) == 0:
                return None

            noteId = note[0]['id']

            threading.Thread(target=NoteService._process_background_tasks, args=(noteId, audio_file)).start()
            print("PAST THIS")

            return noteId
        except Exception as e:
            print("||||||||||EXCEPTION||||||||||")
            print(e)
            return None

    @staticmethod
    def _process_background_tasks(noteId, audio_file):
        try:
            fileId = SupabaseService.upload_file(audio_file, noteId, 'audio-files')
            if fileId is None:
                print(f"Failed to upload file for note {noteId}")
                return
            else:
                print(f"File uploaded successfully for note {noteId}")

            


        except Exception as e:
            print("||||||||||EXCEPTION IN BACKGROUND TASK||||||||||")
            print(e)
