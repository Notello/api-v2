from .SupabaseService import SupabaseService

class NoteService:

    @staticmethod
    def create_audio_note(courseId, userId, form, audio_file, keywords):
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
            
            fileId = SupabaseService.upload_file(audio_file, note[0]['id'], 'audio-files')

            if fileId is None:
                return None

            return note[0]['id']
        except Exception as e:
            print("||||||||||EXCEPTION||||||||||")
            print(e)
            return None