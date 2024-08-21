import logging
from typing import Dict, List, Optional

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.RatelimitService import RatelimitService
from flask_app.services.GraphQueryService import GraphQueryService

from flask_app.constants import COURSEID, NOTEID, FLASHCARD, GPT_4O_MINI
from flask_app.src.shared.common_fn import get_llm


class Answer(BaseModel):
    answer: str = Field(description="The answer text")
    correct: bool = Field(description="A boolean value indicating whether the answer is correct")
    explanation: str = Field(description="A concise, informative explanation of why the answer is correct or incorrect")

class QuizQuestion(BaseModel):
    question: str = Field(description="The question text")
    difficulty: int = Field(description="The difficulty level of the question (1-5, where 1 is easiest and 5 is most difficult)")
    answers: List[Answer] = Field(description="A list of four possible answers")
    chunkIds: List[str] = Field(description="A list of chunk ids that were used to generate the question")

class QuestionResult(BaseModel):
    questions: List[QuizQuestion] = Field(description="A list of questions generated for a given topic pair")

def setup_llm(
    topics: List[str],
    context
):
    system_prompt = """
    You are an advanced quiz question generator, specializing in creating insightful and thought-provoking questions 
    based on provided information. Your task is to generate multiple questions based on a given relationship between concepts and associated text chunks.

    Input:
    - A relationship between two concepts
    - A list of text chunks related to the concepts
    - Number of questions to generate
    - Difficulty level for the questions

    ## Guidelines:
    1. Create questions that explore the relationship between the given concepts.
    2. Use the provided text chunks to inform the questions and answers.
    3. Provide four possible answers for each question, with exactly one marked as correct.
    4. Include clear, concise, and informative explanations for each answer option.
    5. Assign the given difficulty level to each question, where 1 is easiest and 5 is most difficult.
    6. Use natural language in the questions and answers. Avoid mentioning "entities" or "relationships" explicitly.
    7. Ensure that the questions and answers are understandable to someone unfamiliar with the internal structure of the knowledge base.

    ## Important:
    - Do NOT mention or reference chunk IDs in the question text, answer options, or explanations.
    - Only include chunk IDs in the designated 'chunkIds' list for each question.
    - Frame the questions and answers in a way that's natural and easy for a general audience to understand.
    - For explanations, provide meaningful insights that go beyond simply restating the correctness of the answer.
    - Explanations should be one paragraph or less, offering a real understanding of why an answer is correct or incorrect.
    - Compare and contrast the correct answer with the incorrect ones in the explanations when relevant.

    Remember to create questions that are both challenging and answerable based on the provided information.
    """
    
    user_template = f"""
    Please generate {num_questions} quiz questions based on the following information:

    1. Relationship: {source_str} {relationship_type_str} {target_str}

    2. Related Text Chunks:
    {chunks_str}

    3. Difficulty level: {difficulty_str}

    Generate questions that:
    - Explore the relationship between {source_str} and {target_str}
    - Are based on the provided text chunks
    - Each have four possible answers
    - Have the specified difficulty level ({difficulty_str})
    - Are phrased in natural language, avoiding technical terms like "entities" or "relationships"

    ## Important:
    - Do NOT mention or reference chunk IDs in the question text, answer options, or explanations.
    - Only include chunk IDs in the designated 'chunkIds' list for each question.
    - Ensure that the questions and answers are clear and understandable to a general audience.
    - Provide concise but insightful explanations for each answer, highlighting why it's correct or incorrect.
    - Explanations should be one paragraph or less and offer meaningful context or comparisons when appropriate.

    Please provide the questions in the JSON format specified in the system prompt.
    """

    extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(QuestionResult)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

def generate_flashcards(
    topics: List[str],
    chunks: List[Dict[str, str]],
) -> Optional[List[Dict]]:
    try:
        chunks_str = "\n".join([f"Chunk ID: {chunk['id']}, Text: {chunk['text']}" for chunk in chunks])
        topics_str = "\n".join(topics)

        extraction_chain = setup_llm(
            topics=topics,
            context=chunks_str
        )

        results = extraction_chain.invoke({})
        
        return output
    except Exception as e:
        logger.error(f"Error generating quiz questions: {str(e)}")
        raise

class FlashcardService:
    @staticmethod
    def ingest_flashcard(
        courseId, 
        noteId, 
        user_id,
        flashcardId = None
    ):
        specifierParam = NOTEID if noteId else COURSEID
        specifierId = noteId if specifierParam == NOTEID else courseId

        if not flashcardId:
            fladshcardId = SupabaseService.create_flashcards(
                courseId=courseId,
                noteId=noteId,
                userId=user_id
            )

        if not fladshcardId:
            return None

        ContextAwareThread(
            target=FlashcardService.create_flashcards,
            args=(
                courseId, 
                noteId, 
                user_id,
                specifierParam,
                specifierId,
                flashcardId
                )
        ).start()

        return fladshcardId

    def create_flashcards(
            courseId: str, 
            noteId: str, 
            userId: str,
            param: str,
            specifierId: str,
            flashcardId: str
        ):
        ratelimitId = RatelimitService.add_rate_limit(userId=userId, type=FLASHCARD, count=1)

        if ratelimitId is None:
            return None
        
        batch_size = 20

        topic_pairs = get_new_topic_flashcard_pairs_for_param()
        
        flashcards = generate_flashcards(
            topics=topics,
            chunks=chunks
        )
        