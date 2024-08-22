import logging
from flask import request
from flask_restx import Namespace, Resource

from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService

from flask_app.routes.auth import authorizations
from flask_app.routes.middleware import token_required


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
            
            flashcardId = GraphQueryService.get_topic_descriptions_for_param(
                param=param,
                id=id
            )

            return {'flashcardId': flashcardId}, 200

        except Exception as e:
            message = f" Unable to create flashcards, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400