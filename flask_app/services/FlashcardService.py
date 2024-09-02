import logging

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.HelperService import HelperService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.GraphCreationService import GraphCreationService

class FlashcardService():    
    @staticmethod
    def associate_flashcards(
        param: str, 
        id: str, 
        userId: str,
        courseId: str,
        topic_uuids: list,
        setName: str,
        noteId: str
        ):
        if not HelperService.validate_all_uuid4(userId, id):
            logging.error(f'Invalid userId: {userId}, param: {param}, id: {id}')
            return
                
        flashcardId = SupabaseService.create_flashcards(
            noteId=noteId,
            courseId=courseId,
            userId=userId,
            setName=setName
        )

        if not HelperService.validate_all_uuid4(flashcardId):
            return None
        
        flashcards = GraphCreationService.associate_flashcards(
            flashcardId=flashcardId,
            topic_uuids=topic_uuids,
            param=param,
            id=id
        )

        SupabaseService.update_flashcards(flashcardId=flashcardId, key='numFlashcards', value=len(flashcards))

        return flashcards, flashcardId