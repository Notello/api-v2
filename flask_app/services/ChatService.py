from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import json
import logging
from typing import Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.ContextService import ContextService, QuestionModel, QuestionType
from flask_app.services.RatelimitService import RatelimitService

from flask_app.constants import CHAT, COURSEID, GPT_4O_MINI, NOTEID, GPT_4O_MODEL, O1_MINI_MODEL
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
    def question_type_to_enum(question_type):
        if question_type == 'meta_general':
            return QuestionType.META_GENERAL
        elif question_type == 'fact_based':
            return QuestionType.FACT_BASED
        elif question_type == 'problem_solving':
            return QuestionType.PROBLEM_SOLVING
        elif question_type == 'explore':
            return QuestionType.EXPLORE
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
        logging.info(f"noteId: {noteId}")
        logging.info(f"courseId: {courseId}")

        messageId = SupabaseService.add_chat_message(
            chat_room_id=roomId, 
            user_id=None, 
            message=json.dumps({"message": "Gathering Sources", "sources": []}))
        try:
            history = SupabaseService.get_chat_text(chat_room_id=roomId)

            context_type = "note" if param == NOTEID else "course"
            
            question_type = ChatService.get_question_classification(message=message, history=history, context=context_type)

            question_enum = ChatService.question_type_to_enum(question_type=question_type)

            context = ContextService.get_context_nodes(
                question_type=question_enum, 
                query_str=message, 
                history=history,
                param=param,
                id=id
                )
            
            logging.info(f"context: {context}")
                        
            logging.info(f"Chat history: {history}")

            annotated_history = SupabaseService.get_annotated_messages(chat_room_id=roomId)

            SupabaseService.edit_chat_message(message_id=messageId, message=json.dumps({"message": "Generating Reply", "sources": []}))

            reply = ChatService.generate_reply(
                userId=userId, 
                message=message, 
                history=annotated_history, 
                context=context, 
                context_type=context_type,
                question_type=question_enum,
                )
            
            SupabaseService.edit_chat_message(message_id=messageId, message=json.dumps({"message": reply.reply, "sources": reply.sources}))

        except Exception as e:
            logging.error(f"Error generating bot reply: {e}")
            RatelimitService.remove_rate_limit(rateLimitId=ratelimitId)
            SupabaseService.edit_chat_message(message_id=messageId, message=json.dumps({"message": "Error generating reply", "sources": []}))
    
    @staticmethod
    def generate_reply(
        userId, 
        message, 
        history,
        context, 
        context_type,
        question_type
    ):
        extraction_chain = ChatService.setup_llm(
            userMessage=message,
            history=history,
            context=context,
            context_type=context_type,
            question_type=question_type,
        )

        print(question_type)

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
        context_type,
        question_type,
    ):
        logging.info(f"Prompt template: {userMessage}")
        history_str = ""
        userMessage_str = ChatService.escape_template_variables(userMessage)
        if history:
            history_str = ChatService.escape_template_variables('\n'.join(history))

        logging.info(f"History string: {history_str}")

        model_dict = {
            QuestionType.PROBLEM_SOLVING: GPT_4O_MODEL,
            QuestionType.EXPLORE: GPT_4O_MINI,
            QuestionType.META_GENERAL: GPT_4O_MINI,
            QuestionType.FACT_BASED: GPT_4O_MINI
        }

        prompt_template_dict = {
            QuestionType.META_GENERAL: f"""
            You are a question answering assistant. You answer questions about the current {context_type} in general, the user assumes you are an expert in the contents of the {context_type}.

            **General Guidelines**:
            1. Whenever possible, you will answer questions fully from the context of the current {context_type}.
            2. It is acceptable to reasonably extend your answers beyond the given context, however it is VERY important that you inform the user you are doing so.
            3. You will NEVER provide an answer not directly supported by the text without telling the user EXPLICITLY. You must ALWAYS inform the user you are using your best judgement, and that the statement is not backed up by the context.
            4. Use your best judgement to infer the user's intent, it is possible they want a concise answer, or that they want you to engage them in a dialog.
            """,
            QuestionType.FACT_BASED: f"""
            You are a fact based question answering assistant. You answer questions about the current {context_type}, the user assumes you are an expert in the contents of the {context_type}.

            **General Guidelines**:
            1. Whenever possible, you will answer questions fully from the context of the current {context_type}.
            2. You will NEVER provide an answer not directly supported by the text without telling the user EXPLICITLY. You must ALWAYS inform the user you are using your best judgement, and that the statement is not backed up by the context.
            3. Use your best judgement to infer the user's intent, it is possible they want a concise answer, or that they want you to engage them in a dialog.
            """,
            QuestionType.PROBLEM_SOLVING: f"""
            You are a problem assistant. You solve logical or reasoning based problems in a clear and explainable way.

            **General Guidelines**:
            1. You will always make sure your explanations make sense, and are grounded in the context provided.
            2. You will ensure that all steps in your process are clear and understandable, making sure not to gloss over details.
            3. If you do need to make any assumptions, you will inform the user up front, and make them clear at the start of your response.
            """,
            QuestionType.EXPLORE: f"""
            You are a question answering assistant. You answer questions about the current {context_type} with the goal of exploring, the user assumes you are an expert in the contents of the {context_type}.

            **General Guidelines**:
            1. Whenever possible, you will answer questions fully from the context of the current {context_type}.
            2. It is acceptable to reasonably extend your answers beyond the given context, however it is VERY important that you inform the user you are doing so.
            3. Use your best judgement to infer the user's intent, it is possible they want a concise answer, or that they want you to engage them in a dialog.
            4. The user is asking an exploratory question or one that is vague in direction, if appropriate, suggest followup ideas the could explore or questions they could ask based on the context.
            """
        }

        context_prompt = ""
        
        if question_type == QuestionType.META_GENERAL:
            logging.info("in meta")
            summaries_str = ''.join(f"Document Summary {i}:\n {summary}\n\n" for i, summary in enumerate(context['summaries']))
            logging.info("past summaries")
            chunks_str = ''.join(f"Supporting Text {i}:\n Text: {text['text']}\n Chunk UUID: {text['noteId']}\n\n" for i, text in enumerate(context['chunks']))
            logging.info("past chunks")
            concepts_str = ''.join(f"Topic: {topic['name']}, Important Score: {topic['rel_count']}\n" for topic in context['concepts'])
            logging.info("past concepts")

            context_prompt = f"""
            The context provided is on the {context_type} as a whole. It includes summaries of documents in the {context_type}, supporting text from the {context_type}, and the top concepts in the {context_type}.
            You will also be given the current history of the conversation, as well as the current user question.

            Document Summaries:
            {summaries_str}

            Supporting Text:
            {chunks_str}

            Top Concepts:
            {concepts_str}

            Conversation History:
            {history_str}

            User Message:
            {userMessage_str}
            """
        else:
            logging.info("not meta")
            context_str = ""
            logging.info(context)
            if context is not None and len(context) > 0:
                context_items = []
                for key, value in context.items():
                    related_chunks = '\n'.join([f"Chunk UUID: {chunk['id']}, Chunk Text: {chunk['text']}" for chunk in value['related_chunks']])
                    related_concepts = ', '.join([f"{key} {concept['relation_type']} {concept['id']}" for concept in value['related_concepts']])
                    context_items.append(f"Identified Object in Query: {key}\nRelated Chunks:\n{related_chunks}\nRelated Concepts:\n{related_concepts}")
                context_str = '\n\n'.join(context_items)

            context_prompt = f"""
            The context provided is on the {context_type} as a whole. It includes summaries of documents in the {context_type}, supporting text from the {context_type}, and the top concepts in the {context_type}.
            You will also be given the current history of the conversation, as well as the current user question.

            Context:
            {context_str}

            Conversation History:
            {history_str}

            User Message: {userMessage_str}
            """

        question_type_prompt = prompt_template_dict.get(question_type)
        formatting_prompt = """
            You MUST wrap all math or special expressions in $ symbols.
            For example, the message [ \\frac{{\\pi^2}}{{2}} \\approx 4.9348 ] should be formatted as $[ \\frac{{\\pi^2}}{{2}} \\approx 4.9348 ]$.
            You must also start each math expression on a new line, seperated by a \\n character.
            It is EXTREMELY important that you format ALL KaTeX expressions in the message, including inline math, equations, and special symbols in this way.
            """

        PROMPT = question_type_prompt + context_prompt + formatting_prompt

        logging.info(f"prompt: {PROMPT}")

        extraction_llm = get_llm(model_dict[question_type]).with_structured_output(BotReply)
        extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", ChatService.escape_template_variables(PROMPT)),
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
                You are an in context question classifier. Your goal is to determine the type of question the user is asking.
                You are answering questions in the context of a specifc {context}. Please keep this in mind when classifying questions.
                Note on the format of information: It is stored in a Neo4j database, there are concepts, which are related to other concepts. Keep this in mind for the meta classifications.
                
                Please classify the question as one of the following types:
                    META_GENERAL: The user is asking a questions about the {context} in general. This could (but is not limited to) a question about the themes in the {context}, or a question about what the {context} is about.
                    FACT_BASED: The user is asking a question that will need a specific piece of information from the origional text in the {context} to answer.
                    PROBLEM_SOLVING: The user is asking a question that will require logical reasoning and problem solving to answer. This could be (but is not limited to) a math question, or a question that is asking to solve a problem / question in general.
                    EXPLORE: The user is asking a broad, open-ended question to learn about a topic.

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
            return result.question_type
        except Exception as e:
            logging.error(f"Error in get_question_classification: {e}")
            return None, None