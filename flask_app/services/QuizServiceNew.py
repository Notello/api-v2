import asyncio
from enum import Enum
from typing import List
from flask_app.services.SupaGraphService import SupaGraphService
from flask_app.constants import NOTEID

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import GPT_4O_MODEL

class QuestionType(str, Enum):
    DEF_MCQ = "definition based mcq question"
    DEF_MATCH = "definition based matching question"
    APP_MCQ = "application based mcq question"
    APP_SHORT_ANSWER = "application based short answer question"

class Question(BaseModel):
    question_type: QuestionType = Field(description="Type of question.")
    relevant_chunk_ids: List[str] = Field(description="Chunk Ids relevant to the question.")
    relevant_topic_ids: List[str] = Field(description="Topic Ids relevant to the question.")

class SubTopicNode(BaseModel):
    position: int = Field(description="What place in the path the node is.")
    name: str = Field(description="A consise name for the subtopic.")
    description: str = Field(description="A one sentence description of the subtopic and what its questions will cover.")
    questions: List[Question] = Field(description="A list of 6 questions surrounding the sub topic.")

class QuestionResult(BaseModel):
    subnodes: List[SubTopicNode] = Field(description="A list of subtopic nodes in the study path.")

class QuizServiceNew:
    @staticmethod
    def generate_quiz_template(noteId: str, courseId: str):
        top_topics = SupaGraphService.get_top_topics(param=NOTEID, id=noteId, limit=5, courseId=courseId)

        topics = SupaGraphService.get_topics_for_param(param=NOTEID, id=noteId, courseId=courseId)

        tasks = []

        for topic in top_topics:
            task = asyncio.create_task(
                QuizServiceNew.generate_path_for_topic(
                    topic=topic, 
                    topics=topics, 
                    courseId=courseId, 
                    noteId=noteId
                    )
            )
            tasks.append(task)
        print("done !!")


    @staticmethod
    def generate_path_for_topic(topic, topics, courseId, noteId):
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
                
        main_concept = topic_context['start_concept']['id']
        main_concept_uuid = topic_context['start_concept']['uuid']
        related_concepts = topic_context['related_concepts']
        chunks = topic_context['related_chunks']

        print(f"related_concepts: {related_concepts}")
        print(f"chunks: {chunks}")
        print(f"main_concept: {main_concept}")
        print(f"main_concept_id: {main_concept_uuid}")

        chunks_str = ", ".join([f"Chunk Name: {chunk['document_name']}, Chunk UUID: {chunk['chunkId']}, Chunk Text: {chunk['text']}" for chunk in chunks])
        related_concepts_str = ", ".join([f"Concept Name: {concept['id']}, Concept UUID: {concept['uuid']}" for concept in related_concepts])

        context_str = f"Main Concept: {main_concept}\n Main Concept UUID: {main_concept_uuid}\n Related Concepts: {related_concepts_str}\n Chunks: {chunks_str}"

        prompt = ChatPromptTemplate.from_messages([
        ('system', f"""
        You are an expert educational content creator tasked with creating a structured learning path for understanding {main_concept}. Using the provided context, create a study path with 4-5 subtopic nodes that will help a student comprehensively understand this concept.

        Context Information:
        {context_str}

        Requirements for the study path:

        1. Each node should represent a crucial subtopic or aspect of {main_concept}
        2. Nodes should be arranged in a logical learning sequence, from foundational to more advanced concepts
        3. Each node should contain 6-8 questions of varying types
        4. Questions should reference relevant chunk IDs and topic IDs from the provided context
        5. Questions should progress from basic understanding to application within each node

        For each node, provide:
        - Position (1-5)
        - Name (concise identifier for the subtopic)
        - Description (one clear sentence explaining what this node covers)
        - Questions list (6-8 questions with specified types)

        For each question, specify:
        - Question type (choose from: definition based mcq, definition based matching, application based mcq, or application based short answer)
        - Relevant chunk IDs from the provided context
        - Relevant topic IDs from the provided context

        Important Notes:
        - Do not generate the actual questions, only specify their types and relevant IDs
        - Ensure questions reference appropriate chunks that contain relevant information
        - Make sure the progression of nodes builds upon previous knowledge
        - Questions should vary in type to test different levels of understanding
        """)])

        llm = get_llm(GPT_4O_MODEL).with_structured_output(QuestionResult)

        invokable = prompt | llm
        result: QuestionType = invokable.invoke({})

        print(result)

