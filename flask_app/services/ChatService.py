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
from flask_app.services.GraphQueryService import GraphQueryService

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
        elif question_type == 'study_creation':
            return QuestionType.STUDY_CREATION
        elif question_type == 'study_question':
            return QuestionType.STUDY_QUESTION
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

        hasNotes = SupabaseService.has_notes(param=param, id=id)

        if not hasNotes:
            SupabaseService.add_chat_message(
                chat_room_id=roomId, 
                user_id=None, 
                message=json.dumps({"message": "It looks like this workspace is empty. Please make a note to get started!", "sources": []}))
            RatelimitService.remove_rate_limit(rateLimitId=ratelimitId)
            return

        messageId = SupabaseService.add_chat_message(
            chat_room_id=roomId, 
            user_id=None, 
            message=json.dumps({"message": "Gathering Sources", "sources": []}))
        try:
            history = SupabaseService.get_chat_text(chat_room_id=roomId)

            logging.info(f"history: {history}")

            context_type = "note" if param == NOTEID else "course"


            logging.info(f"context_type: {context_type}")
            
            question_type = ChatService.get_question_classification(message=message, history=history, context=context_type)

            question_enum = ChatService.question_type_to_enum(question_type=question_type)

            logging.info(f"question_enum: {question_enum}")

            if question_enum == QuestionType.STUDY_CREATION or question_enum == QuestionType.STUDY_QUESTION:
                logging.info("in study")
                SupabaseService.edit_chat_message(message_id=messageId, message=json.dumps({"message": 
                f"Study material generation and questions are coming soon. In the meantime, check out the quiz and flashcard tabs!", 
                "sources": []}))
                RatelimitService.remove_rate_limit(rateLimitId=ratelimitId)
                return

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
            1. ALWAYS start your response by stating whether the question can be answered using the provided context.
            2. If the question can be fully answered using the context, provide the answer without additional information.
            3. If the question can be partially answered using the context, clearly separate what comes from the context and what doesn't.
            4. If the question cannot be answered using the context at all, state this clearly before providing any answer.
            5. When answering based on your general knowledge, explicitly state that you're doing so.
            6. NEVER pretend that information from your general knowledge is from the context.
            7. Use your best judgement to infer the user's intent, providing a concise or detailed answer as appropriate.
            8. If asked about the source of your information, be honest about whether it came from the context or your general knowledge.
            """,

            QuestionType.FACT_BASED: f"""
            You are a fact based question answering assistant. You answer questions about the current {context_type}, the user assumes you are an expert in the contents of the {context_type}.

            **General Guidelines**:
            1. ALWAYS start your response by stating whether the facts requested can be found in the provided context.
            2. If the facts are in the context, provide them without additional information.
            3. If only some facts are in the context, clearly separate what comes from the context and what doesn't.
            4. If no relevant facts are in the context, state this clearly before providing any answer.
            5. When providing facts from your general knowledge, explicitly state that you're doing so.
            6. NEVER present facts from your general knowledge as if they were from the context.
            7. Use your best judgement to provide a concise or detailed answer as appropriate.
            8. If asked about the source of your information, be transparent about whether it came from the context or your general knowledge.
            """,

            QuestionType.PROBLEM_SOLVING: f"""
            You are a problem assistant. You solve logical or reasoning based problems in a clear and explainable way.

            **General Guidelines**:
            1. ALWAYS start by stating whether the problem can be solved using information from the provided context.
            2. If the context provides all necessary information, solve the problem using only that information.
            3. If the context provides partial information, clearly separate what's based on the context and what isn't.
            4. If the context doesn't help with the problem, state this clearly before attempting to solve it.
            5. When using general problem-solving knowledge, explicitly state that you're doing so.
            6. NEVER pretend that your general problem-solving approach is based on the context if it isn't.
            7. Ensure all steps in your process are clear and understandable.
            8. If you need to make assumptions, state them clearly at the start of your response.
            9. If asked about your problem-solving approach, be honest about whether it came from the context or your general knowledge.
            """,

            QuestionType.EXPLORE: f"""
            You are a question answering assistant. You answer questions about the current {context_type} with the goal of exploring, the user assumes you are an expert in the contents of the {context_type}.

            **General Guidelines**:
            1. ALWAYS start by stating whether the exploration can be based on the provided context.
            2. If the context fully supports the exploration, base your response entirely on it.
            3. If the context partially supports the exploration, clearly separate context-based ideas from additional ones.
            4. If the context doesn't support the exploration, state this clearly before providing any ideas.
            5. When suggesting ideas beyond the context, explicitly state that you're doing so.
            6. NEVER present exploration ideas from your general knowledge as if they were from the context.
            7. Use your best judgement to provide a concise or detailed exploration as appropriate.
            8. Suggest follow-up ideas or questions based on the context when appropriate.
            9. If asked about the source of your exploration ideas, be transparent about whether they came from the context or your general knowledge.
            """
        }

        context_prompt = ""
        
        if question_type == QuestionType.META_GENERAL:
            logging.info("in meta")
            summaries_str = "" if not context else ''.join(f"Document Summary {i}:\n {summary}\n\n" for i, summary in enumerate(context['summaries']))
            logging.info("past summaries")
            chunks_str = "" if not context else ''.join(f"Supporting Text {i}:\n Chunk Text: {text['text']}\n Chunk UUID: {text['noteId']}\n\n" for i, text in enumerate(context['chunks']))
            logging.info("past chunks")
            concepts_str = "" if not context else ''.join(f"Topic: {topic['name']}, Important Score: {topic['rel_count']}\n" for topic in context['concepts'])
            logging.info("past concepts")

            context_prompt = f"""
            The context provided is on the {context_type} as a whole. It includes summaries of documents in the {context_type}, supporting text from the {context_type}, and the top concepts in the {context_type}.
            You will also be given the current history of the conversation, as well as the current user question.
            If no context is provided please inform the user.

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
            If no context is provided please inform the user.

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
        
        sources_prompt = """
            You MUST provide a list of sources that you used to generate your reply. 
            The sources MUST be in the form of a list of Chunk UUIDs, each separated by a comma.
            NEVER MAKE UP SOURCES, ALWAYS PICK FROM THE UUIDS PROVIDED.
        """

        PROMPT = question_type_prompt + context_prompt + formatting_prompt + sources_prompt

        logging.info(f"prompt: {PROMPT}")

        extraction_llm = get_llm(model_dict[question_type]).with_structured_output(BotReply)
        extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", ChatService.escape_template_variables(PROMPT)),
        ])

        return extraction_prompt | extraction_llm

    @staticmethod
    def get_question_classification(message, history, context):
        logging.info(f"in get_question_classification")
        history_str = ""
        if history:
            history_str = ChatService.escape_template_variables('\n'.join(history))
        message = ChatService.escape_template_variables(message)

        logging.info(f"history_str: {history_str}")
        logging.info(f"message: {message}")
        logging.info(f"context: {context}")

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
                    STUDY_CREATION: The user is asking you to make a quiz or flashcard set.
                    STUDY_QUESTION: The user is asking you how they are doing on a quiz, or how good their quiz results are

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