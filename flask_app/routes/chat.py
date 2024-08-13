import logging
from flask_restx import Namespace, Resource
from flask import g


from flask_app.services.AuthService import AuthService
from flask_app.services.HelperService import HelperService
from flask_app.services.RatelimitService import RatelimitService
from flask_app.services.ChatService import ChatService
from flask_app.routes.middleware import token_required
from flask_app.routes.auth import authorizations
from flask_app.constants import CHAT

api = Namespace('chat', authorizations=authorizations)

chat_room_parser = api.parser()
chat_room_parser.add_argument('room_id', type=str, required=False, help='room id')
chat_room_parser.add_argument('user_id', type=str, required=True, help='user id')
chat_room_parser.add_argument('message', type=str, required=True, help='message')
chat_room_parser.add_argument('bot_reply', type=str, required=False, help='answer, chat, or None')

@api.expect(chat_room_parser)
@api.route('/')
class Chat(Resource):
    @api.doc(security="jsonWebToken")
    @token_required
    def post(self):
        args = chat_room_parser.parse_args()
        roomId = args.get('room_id', None)
        userId = args.get('user_id', None)
        message = args.get('message', None)
        botReply = ChatService.chat_type_to_enum(args.get('bot_reply', None))

        reqUserId = g.user_id

        if not HelperService.validate_all_uuid4(userId, reqUserId):
            logging.error(f"Invalid userId: {userId}")
            return {'message': 'Must have userId'}, 400

        if not AuthService.is_authed_for_userId(reqUserId, userId) or not AuthService.can_access_chat_room(userId, roomId):
            logging.error(f"User {userId} is not authorized to create chat room for user {reqUserId}")
            return {'message': 'You do not have permission to create a chat room for this user'}, 400
        
        if RatelimitService.is_rate_limited(userId, CHAT) and botReply is not None:
            logging.error(f"User {reqUserId} has exceeded their chat room rate limit")
            return {'message': 'You have exceeded your chat room rate limit'}, 400
        
        roomId = ChatService.handle_chat(userId=userId, message=message, botReply=botReply, roomId=roomId)

        if not roomId:
            return {'message': 'Error creating chat room'}, 400
        
        return {'roomId': roomId}, 201