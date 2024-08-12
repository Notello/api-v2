from enum import Enum
import logging

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.EntityExtractionService import EntityExtractor

class ChatType(Enum):
    CHAT = 'chat'
    ANSWER = 'answer'

class ChatService():
    @staticmethod
    def chat_type_to_enum(chat_type):
        if chat_type == 'chat':
            return ChatType.CHAT
        elif chat_type == 'answer':
            return ChatType.ANSWER
        else:
            return None

    @staticmethod
    def handle_chat(userId, message, botReply, roomId, history):
        roomId = roomId if roomId is not None else SupabaseService.create_chat_room(userId)
        
        logging.info(f"Chat room created: {roomId}")

        if not roomId:
            return None
        
        SupabaseService.add_chat_message(chat_room_id=roomId, user_id=userId, message=message)

        if botReply is not None:
            ContextAwareThread(
                target=ChatService.generate_bot_reply,
                args=(userId, message, history, botReply)
            ).start()
        
        return roomId
    
    @staticmethod
    def generate_bot_reply(userId, message, history, botReply):
        logging.info(f"Generating bot reply for {userId}")
        context = EntityExtractor.get_context_nodes(query_str=message)

        print(context)
