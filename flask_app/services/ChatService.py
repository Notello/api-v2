from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import json
import logging
from typing import Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.ContextService import ContextService, QuestionModel, BotPrompt
from flask_app.services.RatelimitService import RatelimitService

from flask_app.constants import CHAT, COURSEID, GPT_4O_MINI, NOTEID, GPT_4O_MODEL
from flask_app.src.shared.common_fn import get_llm

pthread = ThreadPoolExecutor(max_workers=10)

class ChatType(Enum):
    CHAT = 'chat'
    ANSWER = 'answer'

class BotReply(BaseModel):
    reply: Optional[str] = Field(
        description="Your reply to the user's message with no citations."
    )
    sources: Optional[List[str]] = Field(
        description="A list of the Chunk UUIDs of the sources used to generate the reply. Do NOT include citations that do not exist or ones we do not provide."
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
    def handle_chat(
        userId, 
        message, 
        botReply, 
        roomId, 
        noteId, 
        courseId,
        userName,
        userProfilePic
        ):
        roomId = roomId if roomId is not None else SupabaseService.create_chat_room(userId)
        
        logging.info(f"Chat room created: {roomId}")

        if not roomId:
            return None
        
        SupabaseService.add_chat_message(
            chat_room_id=roomId, 
            user_id=userId, 
            message=json.dumps({"message": message, "sources": []}),
            user_name=userName,
            pfp=userProfilePic
            )

        if botReply is not None:
            pthread.submit(
                ChatService.generate_bot_reply,
                userId, message, botReply, roomId, noteId, courseId
            )
        
        return roomId
    
    @staticmethod
    def generate_bot_reply(userId, message, botReply, roomId, noteId, courseId):
        ratelimitId = RatelimitService.add_rate_limit(userId=userId, type=CHAT, value=1)
        param = NOTEID if noteId else COURSEID
        id = noteId if noteId else courseId

        logging.info(f"Param: {param}, id: {id}")

        messageId = SupabaseService.add_chat_message(
            chat_room_id=roomId, 
            user_id=None, 
            message=json.dumps({"message": "Gathering Sources", "sources": []}))
        try:
            history = SupabaseService.get_chat_text(chat_room_id=roomId)

            question_type, answer_format = ChatService.get_question_classification(message=message, history=history, context="NOTE" if param == NOTEID else "COURSE")

            context = ContextService.get_context_nodes(
                question_type=question_type, 
                query_str=message, 
                history=history,
                param=param,
                id=id
                )

            logging.info(f"Chat history: {history}")

            annotated_history = SupabaseService.get_annotated_messages(chat_room_id=roomId)

            SupabaseService.edit_chat_message(message_id=messageId, message=json.dumps({"message": "Generating Reply", "sources": []}))

            reply = ChatService.generate_reply(
                userId=userId, 
                message=message, 
                history=annotated_history, 
                context=context, 
                botReply=botReply,
                answer_format=answer_format
                )
            
            SupabaseService.edit_chat_message(message_id=messageId, message=json.dumps({"message": reply.reply, "sources": reply.sources}))

        except Exception as e:
            logging.error(f"Error generating bot reply: {e}")
            RatelimitService.remove_rate_limit(rateLimitId=ratelimitId)
            SupabaseService.edit_chat_message(message_id=messageId, message=json.dumps({"message": "Error generating reply", "sources": []}))
    
    @staticmethod
    def generate_reply(userId, message, history, context, botReply, answer_format):
        extraction_chain = ChatService.setup_llm(
            userMessage=message,
            history=history,
            context=context,
            botReply=botReply,
            answer_format=answer_format
        )

        logging.info("Got chain")

        result = extraction_chain.invoke({})

        logging.info("Got result")

        return result
    
    @staticmethod
    def escape_template_variables(s):
        return s.replace("{", "{{").replace("}", "}}")

    @staticmethod
    def setup_llm(
        userMessage: str,
        history: List[str],
        context,
        botReply,
        answer_format
    ):
        logging.info(f"Prompt template: {userMessage}")
        logging.info(f"context: {context}")
        prompt_template = ""
        history_str = ""
        userMessage_str = ChatService.escape_template_variables(userMessage)
        if history:
            history_str = ChatService.escape_template_variables('\n'.join(history))
        context_str = ""
        if context is not None and len(context) > 0:
            context_items = []
            for key, value in context.items():
                related_chunks = '\n'.join([f"Chunk UUID: {chunk['id']}, Chunk Text: {chunk['text']}" for chunk in value['related_chunks']])
                related_concepts = ', '.join([f"{key} {concept['relation_type']} {concept['id']}" for concept in value['related_concepts']])
                context_items.append(f"Identified Object in Query: {key}\nRelated Chunks:\n{related_chunks}\nRelated Concepts:\n{related_concepts}")
            context_str = '\n\n'.join(context_items)

        logging.info(f"History string: {history_str}")
        logging.info(f"Context string: {context_str}")

        FORMATTING = """
        You MUST wrap all math or special expressions in $ symbols.
        For example, the message [ \\frac{{\\pi^2}}{{2}} \\approx 4.9348 ] should be formatted as $[ \\frac{{\\pi^2}}{{2}} \\approx 4.9348 ]$.
        You must also start each math expression on a new line, seperated by a \\n character.
        It is EXTREMELY important that you format ALL KaTeX expressions in the message, including inline math, equations, and special symbols in this way.
        You will never use the \\text{{}} command in your response.

        FINAL WARNING:
        ALWAYS wrap all math or special expressions, including inline math, equations, matricies, vectors, and special symbols in $ symbols.
        YOU WILL ALWAYS WRAP A MATRIX IN $ SYMBOLS.
        NEVER USE THE \\text{{}} COMMAND IN YOUR RESPONSE.
        """

        if botReply == ChatType.CHAT:
            prompt_template = f"""
            You are an KaTeX based AI assistant that always wraps math output in $$ symbols and engages in a conversation with a user. 
            Your goal is to provide informative and engaging responses, formatted entirely in KaTeX, seperating math output in $ characters. 
            You never ever use the \\text command in your response.
            Use the following information to inform your responses:

            Context:
            {context_str}

            Conversation History:
            {history_str}

            User Message: {userMessage_str}

            Instructions:
            1. Analyze the user's message using the provided context.
            2. Provide a detailed and informative response that addresses the user's query or continues the conversation naturally, using KaTeX for both text and mathematical expressions.
            3. Include relevant information from the context if applicable.
            4. Reference the relationships between the identified objects in the context.
            5. Maintain a friendly and engaging tone throughout the conversation, formatted properly in KaTeX.
            6. If you use information from the context, include the relevant Chunk UUID(s) in the 'sources' field of your response.
            7. Do not provide chunk citations in the reply field, only in the 'sources' field.
            8. If the provided context is not relevant to the user's message, inform the user of that fact, but still provide a response.

            Formatting Guidelines:
            {FORMATTING}
            """
        elif botReply == ChatType.ANSWER:
            prompt_template = f"""You are a KaTeX based AI assistant tasked with providing concise and direct answers to user questions, who always replies in special KaTeX formatting. 
            Your goal is to give accurate and to-the-point responses based on the available information. 
            You always wrap math output in $ characters.
            You never ever use the \\text command in your response.
            Use the following details to inform your answer:

            Context:
            {context_str}

            Conversation History:
            {history_str}

            User Question: {userMessage_str}

            Instructions:
            1. Analyze the user's question using the provided context.
            2. Provide a concise and direct answer that addresses the user's question, formatted using KaTeX.
            3. Include only the most relevant information from the context.
            4. Avoid unnecessary elaboration or tangential information.
            5. If you use information from the context, include the relevant Chunk UUID(s) in the 'sources' field of your response.
            6. Do not provide chunk citations in the reply field, only in the 'sources' field.
            7. If the provided context is not relevant to the user's message, inform the user of that fact, but still provide a response.

            Formatting Guidelines:
            {FORMATTING}
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
    def get_question_classification(message, history, context):
        history_str = ""
        if history:
            history_str = ChatService.escape_template_variables('\n'.join(history))
        message = ChatService.escape_template_variables(message)

        try:
            llm = get_llm(GPT_4O_MODEL).with_structured_output(QuestionModel)
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""
                You are an in context question classifier. Your goal is to determine the type of question the user is asking, and if the output will need any formatting.
                You are answering questions in the context of a specifc {context}. Please keep this in mind when classifying questions.
                Note on the format of information: It is stored in a Neo4j database, there are concepts, which are related to other concepts. Keep this in mind for the meta classifications.
                
                Please classify the question as one of the following types:
                    META_GENERAL: The user is asking a questions about the {context} in general. This could (but is not limited to) a question about the themes in the {context}, or a question about what the {context} is about.
                    META_STATS: The user is asking a question about the statistics of the {context}. This could be (but is not limited to) a question about the number of nodes or concepts in the {context}, or a question about the number of connections a node has. These can also include questions that would need info from a Neo4j Cypher to answer the question.
                    FACT_BASED: The user is asking a question that will need a specific piece of information from the origional text in the {context} to answer.
                    PROBLEM_SOLVING: The user is asking a question that will require logical reasoning and problem solving to answer. This could be (but is not limited to) a math question, or a question that is asking to solve a problem / question in general.
                    EXPLORE: The user is asking a broad, open-ended question to learn about a topic.

                Please classify the needed formatting for the answer as one of the following types:
                    DEFAULT: The answer will not require special formatting.
                    LATEX: The answer will require LaTeX formatting.

                Classify the following question into one of the four question types and one of the four bot prompt categories. Choose the most specific and appropriate ones based on the given criteria.
                """),
                ("human", "Here's the conversation history:"),
                ("human", f"{history_str}"),
                ("human", "And here's the current message:"),
                ("human", f"{message}")
            ])

            invokable = prompt | llm
            result: QuestionModel = invokable.invoke({})
            
            logging.info(f"Question type: {result.question_type}")
            logging.info(f"Bot prompt: {result.answer_format}")
            return result.question_type, result.answer_format
        except Exception as e:
            logging.error(f"Error in get_question_classification: {e}")
            return None, None