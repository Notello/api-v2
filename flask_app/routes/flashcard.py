import logging
from flask import request
from flask_restx import Namespace, Resource

from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.RatelimitService import RatelimitService
from flask_app.services.FlashcardService import FlashcardService

from flask_app.routes.auth import authorizations
from flask_app.routes.middleware import token_required
from flask_app.constants import COURSEID, FLASHCARD, NOTEID


api = Namespace('flashcard', authorizations=authorizations)


@api.route('/get-flashcards-for/<string:param>/<string:id>')
class Flashcard(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self, param, id):
        try:
            user_id = request.user_id

            if not HelperService.validate_all_uuid4(user_id):
                logging.info(f"Invalid user_id: {user_id}")
                return {f'message': 'Invalid user_id'}, 400
            
            if RatelimitService.is_rate_limited(userId=user_id, type=FLASHCARD):
                logging.error(f"User {user_id} has exceeded their flashcard upload rate limit")
                return {'message': 'You have exceeded your flashcard upload rate limit'}, 400
            
            flashcards = FlashcardService.get_flashcard_for_param(
                param=param,
                id=id,
                userId=user_id
            )

            return {'flashcards': flashcards}, 200

        except Exception as e:
            message = f" Unable to create flashcards, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400
        
associate_flashcard_parser = api.parser()

associate_flashcard_parser.add_argument(COURSEID, location='form', 
                        type=str, required=True,
                        help='Course ID associated with the flashcards')
associate_flashcard_parser.add_argument(NOTEID, location='form', 
                        type=str, required=False,
                        help='Note ID associated with the flashcards')

@api.expect(associate_flashcard_parser)
@api.route('/associate-flashcards-for/<string:param>')
class GenerateFlashcardsFor(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self, param, id):
        try:
            args = associate_flashcard_parser.parse_args()
            courseId = args.get(COURSEID, None)
            noteId = args.get(NOTEID, None)

            param, id = NOTEID, noteId if noteId is not None else COURSEID, courseId

            user_id = request.user_id

            if not HelperService.validate_all_uuid4(user_id):
                logging.info(f"Invalid user_id: {user_id}")
                return {f'message': 'Invalid user_id'}, 400
            
            if RatelimitService.is_rate_limited(userId=user_id, type=FLASHCARD):
                logging.error(f"User {user_id} has exceeded their flashcard upload rate limit")
                return {'message': 'You have exceeded your flashcard upload rate limit'}, 400
            
            flashcards = FlashcardService.associate_flashcards(
                noteId=noteId,
                courseId=courseId,
                param=param,
                id=id,
                userId=user_id
            )

            return {'flashcards': flashcards}, 200
        except Exception as e:
            message = f" Unable to create flashcards, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400