from enum import Enum
import json
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
    reply: Optional[str] = Field(
        description="Your reply to the user's message with no citations."
    )
    sources: Optional[List[str]] = Field(
        description="A list of the Chunk UUIDs of the sources used to generate the reply."
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
    def handle_chat(userId, message, botReply, roomId):
        roomId = roomId if roomId is not None else SupabaseService.create_chat_room(userId)
        
        logging.info(f"Chat room created: {roomId}")

        if not roomId:
            return None
        
        SupabaseService.add_chat_message(chat_room_id=roomId, user_id=userId, message=json.dumps({"message": message, "sources": []}))

        if botReply is not None:
            ContextAwareThread(
                target=ChatService.generate_bot_reply,
                args=(userId, message, botReply, roomId)
            ).start()
        
        return roomId
    
    @staticmethod
    def generate_bot_reply(userId, message, botReply, roomId):
        context = EntityExtractor.get_context_nodes(query_str=message)

        history = SupabaseService.get_chat_history(chat_room_id=roomId)

        logging.info(f"Chat history: {history}")

        reply = ChatService.generate_reply(userId=userId, message=message, history=history, context=context, botReply=botReply)

        RatelimitService.add_rate_limit(userId=userId, type=CHAT, value=1)
        SupabaseService.add_chat_message(chat_room_id=roomId, user_id=None, message=json.dumps(reply))
    
    @staticmethod
    def generate_reply(userId, message, history, context, botReply):
        extraction_chain = ChatService.setup_llm(
            userMessage=message,
            history=history,
            context=context,
            botReply=botReply
        )

        result = extraction_chain.invoke({})

        return {
            'message': result.reply,
            'sources': result.sources
        }

    @staticmethod
    def setup_llm(
        userMessage: str,
        history: List[str],
        context,
        botReply
    ):
        prompt_template = ""
        history_str = '\n'.join(history)
        context_str = ""
        if len(context) > 0:
            context_items = []
            for key, value in context.items():
                related_chunks = '\n'.join([f"Chunk UUID: {chunk['id']}, Chunk Text: {chunk['text']}" for chunk in value['related_chunks']])
                related_concepts = ', '.join([f"{concept['id']}" for concept in value['related_concepts']])
                context_items.append(f"Identified Object in Query: {key}\nRelated Chunks:\n{related_chunks}\nRelated Concepts:\n{related_concepts}")
            context_str = '\n\n'.join(context_items)

        if botReply == ChatType.CHAT:
            prompt_template = f"""You are an AI assistant engaged in a conversation with a user. Your goal is to provide informative and engaging responses that encourage further learning and discussion about the topic at hand. Use the following information to inform your responses:

            Context:
            {context_str}

            {f'Conversation History:\n{history_str}' if history_str else ''}

            User Message: {userMessage}

            Instructions:
            1. Analyze the user's message and the provided context.
            2. Provide a detailed and informative response that addresses the user's query or continues the conversation naturally.
            3. Include relevant information from the context if applicable.
            4. Ask follow-up questions or suggest related topics to encourage further discussion.
            5. Maintain a friendly and engaging tone throughout the conversation.
            6. If you use information from the context, include the relevant Chunk UUID(s) in the 'sources' field of your response.
            7. Do not provide chunk citations in your reply, only in the 'sources' field.
            """
        elif botReply == ChatType.ANSWER:
            prompt_template = f"""You are an AI assistant tasked with providing concise and direct answers to user questions. Your goal is to give accurate and to-the-point responses based on the available information. Use the following details to inform your answer:

            Context:
            {context_str}

            User Question: {userMessage}

            Instructions:
            1. Analyze the user's question and the provided context.
            2. Provide a concise and direct answer that addresses the user's question.
            3. Include only the most relevant information from the context.
            4. Avoid unnecessary elaboration or tangential information.
            5. If the question cannot be answered with the given context, state that clearly.
            6. If you use information from the context, include the relevant Chunk UUID(s) in the 'sources' field of your response.
            7. Do not provide chunk citations in your reply, only in the 'sources' field.
            """
        else:
            logging.error(f'Invalid botReply: {botReply}')
            return
        
        logging.info(f"Prompt template: {prompt_template}")
    
        extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(BotReply)
        extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template),
        ])
        
        return extraction_prompt | extraction_llm