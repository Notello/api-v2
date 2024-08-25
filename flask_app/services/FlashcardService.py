import logging

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.HelperService import HelperService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.GraphCreationService import GraphCreationService

class FlashcardService():
    @staticmethod
    def get_flashcard_for_param(param: str, id: str, userId: str):
        return GraphQueryService.get_flashcards(
            param=param,
            id=id
        )
    
    @staticmethod
    def associate_flashcards(
        param: str, 
        id: str, 
        userId: str,
        courseId: str,
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
            param=param,
            id=id
        )

        return flashcards