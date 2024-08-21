import logging
from flask import request
from flask_restx import Namespace, Resource

from flask_app.services.FlashcardService import FlashcardService
from flask_app.services.HelperService import HelperService

from flask_app.routes.auth import authorizations
from flask_app.routes.middleware import token_required


api = Namespace('flashcard', authorizations=authorizations)

create_flashcard_parser = api.parser()

create_flashcard_parser.add_argument('courseId', location='form', 
                        type=str, required=True,
                        help='Course ID associated with the flashcard')
create_flashcard_parser.add_argument('noteId', location='form', 
                        type=str, required=False,
                        help='Note ID associated with the flashcard')
create_flashcard_parser.add_argument('flashcardId', location='form', 
                        type=str, required=False,
                        help='Flashcard ID associated with the flashcard')

@api.expect(create_flashcard_parser)
@api.route('/get-new-flashcards')
class Flashcard(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        try:
            args = create_flashcard_parser.parse_args()
            courseId = args.get('courseId', None)
            noteId = args.get('noteId', None)
            flashcardId = args.get('flashcardId', None)
            user_id = request.user_id
            logging.info(f"Create flashcards for {courseId}, {noteId}")

            if not HelperService.validate_all_uuid4(courseId):
                logging.info(f"Invalid courseId or noteId: {courseId}")
                return {f'message': 'Invalid courseId or noteId'}, 400
            
            flashcardId = FlashcardService.ingest_flashcard(courseId=courseId, noteId=noteId, user_id=user_id, flashcardId=flashcardId)

            return {'flashcardId': flashcardId}, 200

        except Exception as e:
            message = f" Unable to create flashcards, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400