from enum import Enum
import logging
from typing import Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.EntityExtractionService import EntityExtractor
from flask_app.services.RatelimitService import RatelimitService

from flask_app.constants import CHAT, GPT_4O_MINI
from flask_app.src.shared.common_fn import get_llm

class ChatType(Enum):
    CHAT = 'chat'
    ANSWER = 'answer'

class BotReply(BaseModel):
    reply: Optional[List[str]] = Field(
        description="Your reply to the user's message."
    )
    sources: Optional[List[str]] = Field(
        description="A list of the UUIDs of the sources used to generate the reply."
    )

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
                args=(userId, message, history, botReply, roomId)
            ).start()
        
        return roomId
    
    @staticmethod
    def generate_bot_reply(userId, message, history, botReply, roomId):
        logging.info(f"Generating bot reply for {userId}")
        context = EntityExtractor.get_context_nodes(query_str=message)

        reply = ChatService.generate_bot_reply(userId=userId, message=message, history=history, context=context, botReply=botReply)

        RatelimitService.add_rate_limit(userId=userId, type=CHAT, value=1)
        SupabaseService.add_chat_message(chat_room_id=roomId, user_id=userId, message=reply)
    
    @staticmethod
    def generate_bot_reply(userId, message, history, context, botReply):
        extraction_chain = ChatService.setup_llm(
            userMessage=message,
            history=history,
            context=context,
            botReply=botReply
        )

        result = extraction_chain.invoke({})

    @staticmethod
    def setup_llm(
        userMessage: str,
        history: List[str],
        context: Dict[str, str],
        botReply: str
    ):
        prompt_template = ""

        if botReply == ChatType.CHAT:
            prompt_template = f"""

            """
        elif botReply == ChatType.ANSWER:
            prompt_template = f"""

            """
        else:
            logging.error(f'Invalid botReply: {botReply}')
            return
    
        extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(BotReply)
        extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
        ])
        
        return extraction_prompt | extraction_llm
