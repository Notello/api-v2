from enum import Enum
import json
import logging
from typing import Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.ContextService import ContextService, QuestionModel
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
        ratelimitId = RatelimitService.add_rate_limit(userId=userId, type=CHAT, value=1)
        try:
            question_type = ChatService.get_question_type(message)

            context = ContextService.get_context(question_type=question_type, query_str=message)

            history = SupabaseService.get_chat_history(chat_room_id=roomId)

            logging.info(f"Chat history: {history}")

            reply = ChatService.generate_reply(userId=userId, message=message, history=history, context=context, botReply=botReply)

            SupabaseService.add_chat_message(chat_room_id=roomId, user_id=None, message=json.dumps(reply))
        except Exception as e:
            logging.error(f"Error generating bot reply: {e}")
            RatelimitService.remove_rate_limit(rateLimitId=ratelimitId)
            SupabaseService.add_chat_message(chat_room_id=roomId, user_id=None, message=json.dumps({"message": "Sorry, I'm having trouble generating a reply at the moment. Please try again later."}))
    
    @staticmethod
    def generate_reply(userId, message, history, context, botReply):
        # extraction_chain = ChatService.setup_llm(
        #     userMessage=message,
        #     history=history,
        #     context=context,
        #     botReply=botReply
        # )

        # result = extraction_chain.invoke({})

        # return {
        #     'message': result.reply,
        #     'sources': result.sources
        # }

        return {
            'message': "dud",
            'sources': []
        }
    
    @staticmethod
    def escape_template_variables(s):
        return s.replace("{", "{{").replace("}", "}}")

    @staticmethod
    def setup_llm(
        userMessage: str,
        history: List[str],
        context,
        botReply
    ):
        prompt_template = ""
        history_str = ChatService.escape_template_variables('\n'.join(history))
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

            Conversation History:
            {history_str}

            User Message: {userMessage}

            Instructions:
            1. Analyze the user's message and the provided context.
            2. Provide a detailed and informative response that addresses the user's query or continues the conversation naturally.
            3. Include relevant information from the context if applicable.
            4. Ask follow-up questions or suggest related topics to encourage further discussion.
            5. Maintain a friendly and engaging tone throughout the conversation.
            6. If you use information from the context, include the relevant Chunk UUID(s) in the 'sources' field of your response.
            7. Do not provide chunk citations in the reply field, only in the 'sources' field.
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
            7. Do not provide chunk citations in the reply field, only in the 'sources' field.
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

    @staticmethod
    def get_question_type(message):
        try:
            llm = get_llm(GPT_4O_MINI).with_structured_output(QuestionModel)

            prompt = ChatPromptTemplate.from_messages([
                ("system", """
                You are a question classifier. Your goal is to determine the type of question the user is asking based on the following criteria:

                1. EXPLORE: The user is asking a broad, open-ended question to learn about a topic. 
                   Example: "Tell me about the French Revolution."

                2. ANSWER: The user is seeking a specific, factual answer or solution to a problem. This includes homework-like questions or requests for direct answers.
                   Examples: "What is the capital of France?", "Solve for x in the equation 2x + 3 = 11", "Answer question 1"

                3. RELATIONSHIP: The user is asking about connections, comparisons, or interactions between two or more entities, concepts, or events.
                   Example: "How did World War I influence World War II?"

                4. FOLLOWUP: The user is referring to or building upon information from a previous part of the conversation. This often includes pronouns or context-dependent phrases.
                   Example: "Can you elaborate on that last point?", "What about its impact on the economy?"

                Classify the following question into one of these four categories. If the question could fit multiple categories, choose the most specific and appropriate one based on the given criteria.
                """),
                ("user", message)
            ])

            invokable = prompt | llm

            result: QuestionModel = invokable.invoke({})

            logging.info(f"Question type: {result.question_type}")

            return result.question_type
        except Exception as e:
            logging.error(f"Error in get_question_type: {e}")
            return None