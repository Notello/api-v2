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
        topics: list,
        noteId: str = None
        ):
        if not HelperService.validate_all_uuid4(userId, id):
            logging.error(f'Invalid userId: {userId}, param: {param}, id: {id}')
            return
                
        flashcardId = SupabaseService.create_flashcards(
            noteId=noteId,
            courseId=courseId,
            userId=userId
        )

        if not HelperService.validate_all_uuid4(flashcardId):
            return None
        
        flashcards = GraphCreationService.associate_flashcards(
            flashcardId=flashcardId,
            topic_uuids=topics,
            param=param,
            id=id
        )

        return flashcards