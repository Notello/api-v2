import asyncio
from enum import Enum
from typing import List
from flask_app.services.SupaGraphService import SupaGraphService
from flask_app.services.SupabaseService import SupabaseService
from concurrent.futures import ThreadPoolExecutor

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from pprint import pprint

from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import (
    GPT_4O_MINI, 
    GPT_4O_MODEL, 
    QUESTION_CHUNK_TABLE_NAME, 
    QUESTION_TOPIC_TABLE_NAME, 
    QUIZ_NODE_TABLE_NAME, 
    NODE_QUESTION_TABLE_NAME, 
    NOTE_QUIZ_CARD_TABLE_NAME,
    ID,
    NOTEID,
    NOTE_TABLE_NAME
)

from uuid import uuid4

class QuestionType(str, Enum):
    DEF_MCQ = "definition based mcq question"
    DEF_MULTI_SELECT_MCQ = "definition based mcq multi select question"
    DEF_MATCH = "definition based matching question"
    APP_MCQ = "application based mcq question"
    # APP_SHORT_ANSWER = "application based short answer question"

def question_type_to_enum(question_type):
    if question_type == "definition based mcq question":
        return QuestionType.DEF_MCQ
    elif question_type == "definition based mcq multi select question":
        return QuestionType.DEF_MULTI_SELECT_MCQ
    elif question_type == "definition based matching question":
        return QuestionType.DEF_MATCH
    elif question_type == "application based mcq question":
        return QuestionType.APP_MCQ
    # elif question_type == "application based short answer question":
    #     return QuestionType.APP_SHORT_ANSWER
    else:
        return None
    
## Question Path Generation

class Question(BaseModel):
    question_type: QuestionType = Field(description="Type of question.")
    question_description: str = Field(description="What the question is meant to test.")

class SubTopicNode(BaseModel):
    position: int = Field(description="What place in the path the node is.")
    name: str = Field(description="A consise name for the subtopic.")
    description: str = Field(description="A one sentence description of the subtopic and what its questions will cover.")
    questions: List[Question] = Field(description="A list of 6 questions surrounding the sub topic.")

class QuestionResult(BaseModel):
    subnodes: List[SubTopicNode] = Field(description="A list of subtopic nodes in the study path.")
    mainConceptDesc: str = Field(description="A description of what is covered surrounding the main concept.")

## Individual Question Generation

class McqAnswer(BaseModel):
    answer: str = Field(description="The answer text")
    correct: bool = Field(description="A boolean value indicating whether the answer is correct")
    explanation: str = Field(description="A concise, informative explanation of why the answer is correct or incorrect")

class McqQuestion(BaseModel):
    question: str = Field(description="The question text")
    answers: List[McqAnswer] = Field(description="A list of four possible answers")

class MatchingAnswer(BaseModel):
    term: str = Field(description="The term to be matched to a definition")
    definition: str = Field(description="The descripiton to be matched to a term")

class MatchingQuestion(BaseModel):
    question: str = Field(description="The question text")
    answers: List[MatchingAnswer] = Field(description="A list of 6 possible answers")

class ShortAnswerQuestion(BaseModel):
    question: str = Field(description="The question text")
    rubric: str = Field(description="An outline of what the correct answer could look like, and what the wrong one might look like")

## FRQ Grading

class FrqResponse(BaseModel):
    correct: bool = Field(description="If the answer is overall correct or not")
    explanation: str = Field(description="An explanation as to why the answer is correct or incorrect")

class QuizServiceNew:
    @staticmethod
    def get_context_str(
        context
    ):
        main_concept = context['start_concept']['id']
        main_concept_uuid = context['start_concept']['uuid']
        related_concepts = context['related_concepts']
        chunks = context['related_chunks']

        chunks_str = ", ".join([f"Chunk Name: {chunk['document_name']}, Chunk UUID: {chunk['chunkId']}, Chunk Text: {chunk['text']}" for chunk in chunks])
        related_concepts_str = ", ".join([f"Concept Name: {concept['id']}, Concept UUID: {concept['uuid']}" for concept in related_concepts])

        context_str = f"Main Concept: {main_concept}\n Main Concept UUID: {main_concept_uuid}\n Related Concepts: {related_concepts_str}\n Chunks: {chunks_str}"

        return context_str, main_concept


    @staticmethod
    async def generate_quiz_template(noteId: str, courseId: str, userId: str):
        top_topics = SupaGraphService.get_top_topics(param=NOTEID, id=noteId, limit=5, courseId=courseId)
        topics = SupaGraphService.get_topics_for_param(param=NOTEID, id=noteId, courseId=courseId)
        noteSummary = SupabaseService.get_obj_by_id(
            id=noteId,
            param=ID,
            table_name=NOTE_TABLE_NAME,
            single=True
        )['summary']

        futures = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            for topic in top_topics:
                    futures.append(
                        executor.submit(
                            QuizServiceNew.generate_path_for_topic,
                                topic=topic, 
                                topics=topics, 
                                courseId=courseId, 
                                noteId=noteId,
                                userId=userId,
                                noteSummary=noteSummary
                        ))

        print("done !!")

    @staticmethod
    def generate_path_for_topic(
        topic, 
        topics, 
        courseId, 
        noteId, 
        userId,
        noteSummary
    ):
        print(f"in generate path, topic: {topic}")
        print(f"topicId: {topic['id']}")

        topic_context = SupaGraphService.get_topic_context(
            topicId=topic['id'], 
            topicName=topic['name'],
            num_chunks=5, 
            num_related_concepts=20, 
            courseId=courseId,
            topics=topics,
            param=NOTEID,
            id=noteId
        )
                
        context_str, main_concept = QuizServiceNew.get_context_str(context=topic_context)

        prompt = ChatPromptTemplate.from_messages([
        ('system', f"""
        You are an expert educational content creator tasked with creating a structured learning path for understanding {main_concept} in the context of a note. 
        Using the provided context, and note summary, create a study path with 4-5 subtopic nodes that will help a student comprehensively understand this concept in the context of the note.

        Note Summary:
        {noteSummary}

        Context Information:
        {context_str}

        Requirements for the study path:

        1. Each node should represent a crucial subtopic or aspect of {main_concept}
        2. The questions should be in the general context of the note summary, NOT on the concepts in general
        3. Nodes should be arranged in a logical learning sequence, from foundational to more advanced concepts
        4. Each node should contain 6-8 questions of varying types
        5. Questions should progress from basic understanding to application within each node

        For each node, provide:
        - Position (1-5)
        - Name (concise identifier for the subtopic)
        - Description (one clear sentence explaining what this node covers)
        - Questions list (6-8 questions with specified types)

        For each question, specify:
        - Question type (choose from: definition based mcq, definition based multi select mcq, definition based matching, application based mcq)
        - Question description, a description of what the question is meant to test in the user.

        Important Notes:
        - Do not generate the actual questions, only specify their types and descriptions of what they are about
        - Make sure the progression of nodes builds upon previous knowledge
        - Questions should vary in type to test different levels of understanding
        - DO NOT use the word 'node' in the node or question descriptions, this a purely internal term and not one the end user should see
        """)])

        llm = get_llm(GPT_4O_MODEL).with_structured_output(QuestionResult)

        invokable = prompt | llm
        result: QuestionResult = invokable.invoke({})

        print("RESULT")
        pprint(result)

        nodes = []
        nodeQuestions = []

        noteQuizCardId = str(uuid4())

        for node in result.subnodes:
            nodeId = str(uuid4())

            nodes.append({
                "id": nodeId,
                "mainConceptId": topic['id'],
                "noteQuizCardId": noteQuizCardId,
                "position": node.position,
                "name": node.name,
                "description": node.description
            })

            for question in node.questions:
                questionId = str(uuid4())

                nodeQuestions.append({
                    "id": questionId,
                    "quizNodeId": nodeId,
                    "questionType": question.question_type,
                    "questionDesc": question.question_description
                })

        SupabaseService.insert_batch(
            data=[{
                "id": noteQuizCardId,
                "userId": userId,
                "courseId": courseId,
                "noteId": noteId,
                "mainConceptName": topic['name'],
                "description": result.mainConceptDesc
            }],
            table_name=NOTE_QUIZ_CARD_TABLE_NAME
        )

        # print(f"nodes data: {nodes}")

        SupabaseService.insert_batch(
            data=nodes,
            table_name=QUIZ_NODE_TABLE_NAME
        )

        # print(f"node questions: {nodeQuestions}")

        SupabaseService.insert_batch(
            data=nodeQuestions,
            table_name=NODE_QUESTION_TABLE_NAME
        )

    @staticmethod
    def generate_questions_for_node(
        nodeId,
        noteId,
        courseId
    ):
        questions_context = SupabaseService.get_node_context(
            nodeId=nodeId,
            noteId=noteId,
            courseId=courseId
        )

        noteSummary = SupabaseService.get_obj_by_id(
            id=noteId,
            param=ID,
            table_name=NOTE_TABLE_NAME,
            single=True
        )['summary']

        futures = []

        questions = questions_context['questions']
        context = questions_context['context']

        with ThreadPoolExecutor(max_workers=10) as executor:
            for question in questions:
                    futures.append(
                        executor.submit(
                            QuizServiceNew.generate_question,
                            question,
                            context,
                            noteSummary,
                            nodeId
                        ))
                    
    @staticmethod
    def generate_question(
        question,
        context,
        noteSummary,
        nodeId
    ):
        print("node")

        context_str, main_concept = QuizServiceNew.get_context_str(context=context)

        qType = question_type_to_enum(question['questionType'])

        if qType is None:
            return None

        prompt, llm = QuizServiceNew.get_question_inputs(
            question=question,
            qType=qType,
            context_str=context_str,
            noteSummary=noteSummary
        )

        invokable = prompt | llm
        result = invokable.invoke({})

        print(f"result: {result}")

        QuizServiceNew.insert_question(
            nodeQuestionId=question['id'],
            result=result,
            qType=qType
        )
    
    @staticmethod
    def insert_question(
        nodeQuestionId,
        result,
        qType
    ):
        answers = []

        print("in insert question")

        if qType == QuestionType.APP_SHORT_ANSWER:
            answers = [{
                "nodeQuestionId": nodeQuestionId, 
                "explanation": result.rubric,
                "type": qType.value
            }]
        elif qType == QuestionType.DEF_MATCH:
            answers = [{
                "nodeQuestionId": nodeQuestionId, 
                "answer": answer.term, 
                "explanation": answer.definition,
                "type": qType.value
            } for answer in result.answers]
        else:
            answers = [{
                "nodeQuestionId": nodeQuestionId, 
                "answer": answer.answer, 
                "explanation": answer.explanation, 
                "correct": answer.correct,
                "type": qType.value
            } for answer in result.answers]

        print(f"answers: {answers}")

        SupabaseService.update_node_question(
            nodeQuestionId=nodeQuestionId,
            question=result.question
        )

        SupabaseService.insert_node_question_answer(
            answers=answers
        )

    @staticmethod
    def get_question_inputs(
        question,
        qType,
        context_str,
        noteSummary
    ):
        structuredOutputType, context_prompt = None, ""

        if qType == QuestionType.DEF_MCQ:
            structuredOutputType = McqQuestion
            context_prompt = f"""
            You are a single answer multiple choice creation bot. You make multiple choice questions with clear answers and explanations.
            You will produce 4 answers, with explanations as to why each option is right or wrong.
            You will produce meaningfully different answers, speciffically you should avoid the following type of response:
            Option 1: Correct because it matches reason A
            Option 2: Incorrect because it doesn't match reason A
            Option 3: Incorrect because it doesn't match reason A
            Option 4: Incorrect because it doesn't match reason A

            Your options and explanations should be comprehensive, not surface level.

            Your question should be based on the description given below:
            {question['questionDesc']}

            Use the following context to create the question:
            {context_str}

            Use the following note summary to provide the general context the question should be in:
            {noteSummary}
            """
        elif qType == QuestionType.DEF_MATCH:
            structuredOutputType = MatchingQuestion
            context_prompt = f"""
            You are a term definition matching question creation bot.
            You will produce answers that clearly make sense in the context of the note summary.

            Your question should be based on the description given below:
            {question['questionDesc']}

            Use the following context to create the question:
            {context_str}

            Use the following note summary to provide the general context the question should be in:
            {noteSummary}
            """
        elif qType == QuestionType.DEF_MULTI_SELECT_MCQ:
            structuredOutputType = McqQuestion
            context_prompt = f"""
            You are a multi answer multiple choice creation bot. You make multiple choice questions with clear answers and explanations.
            You will produce 5 answers, with explanations as to why each option is right or wrong.
            You will produce meaningfully different answers, speciffically you should avoid the following type of response:
            Option 1: Correct because it matches reason A
            Option 2: Incorrect because it doesn't match reason A
            Option 3: Incorrect because it doesn't match reason A
            Option 4: Correct because it matches reason A
            Option 5: Incorrect because it doesn't match reason A

            Your options and explanations should be comprehensive, not surface level.

            Your question should be based on the description given below:
            {question['questionDesc']}

            Use the following context to create the question:
            {context_str}

            Use the following note summary to provide the general context the question should be in:
            {noteSummary}
            """
        elif qType == QuestionType.APP_MCQ:
            structuredOutputType = McqQuestion
            context_prompt = f"""
            You are an application based single answer multiple choice creation bot. You make application based multiple choice questions with clear answers and explanations.
            You will produce 4 answers, with explanations as to why each option is right or wrong.
            You will produce meaningfully different answers, speciffically you should avoid the following type of response:
            Option 1: Correct because it matches reason A
            Option 2: Incorrect because it doesn't match reason A
            Option 3: Incorrect because it doesn't match reason A
            Option 4: Incorrect because it doesn't match reason A

            Your options and explanations should be comprehensive, not surface level.

            Your question should be based on the description given below:
            {question['questionDesc']}

            Use the following context to create the question:
            {context_str}

            Use the following note summary to provide the general context the question should be in:
            {noteSummary}
            """
        elif qType == QuestionType.APP_SHORT_ANSWER:
            structuredOutputType = ShortAnswerQuestion
            context_prompt = f"""
            You are an application based short answer question creation bot. You provide clear and consise questions that will take 1-2 paragraphs to answer.
            The question should be application based, and it should use the context of the note summary to ground the question.

            Your question should be based on the description given below:
            {question['questionDesc']}

            Use the following context to create the question:
            {context_str}

            Use the following note summary to provide the general context the question should be in:
            {noteSummary}
            """
        
        print("wow")

        llm = get_llm(GPT_4O_MINI).with_structured_output(structuredOutputType)
        prompt = ChatPromptTemplate.from_messages([('system', context_prompt)])

        return prompt, llm
    
    @staticmethod
    def grade_frq_question(
        question,
        answer,
        mainConceptId,
        mainConceptName,
        noteId,
        courseId
    ):
        topics = SupaGraphService.get_topics_for_param(param=NOTEID, id=noteId, courseId=courseId)

        topic_context = SupaGraphService.get_topic_context(
            topicId=mainConceptId, 
            topicName=mainConceptName,
            num_chunks=5, 
            num_related_concepts=20, 
            courseId=courseId,
            topics=topics,
            param=NOTEID,
            id=noteId
        )
                
        context_str, main_concept = QuizServiceNew.get_context_str(context=topic_context)

        prompt = ChatPromptTemplate.from_messages([
        ('system', f"""
        You are an free response question grader. You provide accurate and insightful evaluations of free response questions based on the provided context.

        Question:
        {question}

        User Answer:
        {answer}

        Context:
        {context_str}
        """)])

        llm = get_llm(GPT_4O_MINI).with_structured_output(FrqResponse)

        invokable = prompt | llm
        result: FrqResponse = invokable.invoke({})

        return {
            "correct": result.correct,
            "explanation": result.explanation
        }
