import logging
from typing import Dict

from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from retry import retry

from pprint import pprint

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.GraphCreationService import GraphCreationService
from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import DEFAULT_COMMUNITIES, GPT_35_TURBO_MODEL, MIXTRAL_MODEL, LLAMA_8_MODEL, GPT_4O_MINI

logger = logging.getLogger(__name__)

class Answer(BaseModel):
    answer: str = Field(description="The answer text")
    correct: bool = Field(description="A boolean value indicating whether the answer is correct")
    explanation: str = Field(description="A brief explanation of why the answer is correct or incorrect")

class QuizQuestion(BaseModel):
    question: str = Field(description="The question text")
    difficulty: int = Field(description="The difficulty level of the question (1-5, where 1 is easiest and 5 is most difficult)")
    answers: List[Answer] = Field(description="A list of four possible answers, each answer is represented by a dictionary")
    chunkIds: List[str] = Field(description="A list of chunk ids that you used to generate the questions")
    topics: List[str] = Field(description="A list of topics that you used to generate the questions")

class QuizQuestions(BaseModel):
    questions: List[QuizQuestion] = Field(
        description="A list of questions, where each question is represented by a dictionary"
    )

def setup_llm(
        relationship_str, 
        raw_text_str, 
        average_difficulty, 
        num_questions,
        topics_to_focus_on
):
    system_prompt = """
    You are an advanced quiz question generator, specializing in creating insightful and thought-provoking questions 
    based on provided information. Your task is to generate questions tailored to specified topics, a general difficulty level, and number of questions.

    Input:
    - A list of topics to focus on
    - A list of relationships between concepts
    - A list of raw text chunks
    - Average Desired Difficulty level (1-5, where 1 is easiest and 5 is most difficult)
    - Number of questions to generate

    ## Guidelines:
    1. Focus primarily on the provided topics when generating questions.
    2. Ensure questions are diverse and cover different aspects of the provided information within the specified topics.
    3. Adjust complexity based on the given average difficulty level, but assign each question its own difficulty rating.
    4. Use the relationships and raw text to craft accurate and relevant questions.
    5. Provide clear and concise explanations for each answer option.
    6. Include relevant chunk IDs and topics for each question.
    7. Ensure that exactly one answer per question is marked as correct.
    8. Always provide 4 possible answers for each question.
    9. Assign a difficulty level (1-5) to each individual question, considering the average difficulty provided.
    10. Use natural language in questions and answers. Avoid mentioning "entities" or "relationships" explicitly.
    11. Ensure that questions and answers are understandable to someone unfamiliar with the internal structure of the knowledge base.

    ## Important:
    - Do NOT mention or reference chunk IDs, entities, or relationships in the question text, answer options, or explanations.
    - Only include chunk IDs in the designated 'chunkIds' list for each question.
    - Frame questions and answers in a way that's natural and easy for a general audience to understand.

    Remember to maintain a balance between challenging the quiz-taker and ensuring the questions are answerable based on the provided information.
    """
    
    user_template = f"""
    Please generate a quiz based on the following information:

    1. Topics to Focus On: {topics_to_focus_on}

    2. Topic Relationships: {relationship_str}

    3. Raw Text Chunks: {raw_text_str}

    4. Quiz Parameters:
    - Average Difficulty Level: {average_difficulty} (1-5, where 1 is easiest and 5 is most difficult)
    - Number of Questions: {num_questions}

    Generate the specified number of questions, ensuring they:
    - Primarily focus on the provided topics
    - Are based on the provided concept relationships and raw text
    - Each have four possible answers
    - Have an individual difficulty rating (1-5) for each question, considering the average difficulty provided
    - Cover aspects of the given information within the specified topics
    - Include relevant chunk IDs and topics for each question
    - Are phrased in natural language, avoiding technical terms like "entities" or "relationships"

    ## Important:
    - Do NOT mention or reference chunk IDs, entities, or relationships in the question text, answer options, or explanations.
    - Only include chunk IDs in the designated 'chunkIds' list for each question.
    - Ensure that questions and answers are clear and understandable to a general audience.

    Please provide the questions in the JSON format specified in the system prompt.
    """

    extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(QuizQuestions)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

@retry(tries=3, delay=2)
def generate_quiz_questions(
    relationships: List[Dict[str, str]],
    raw_texts: List[Dict[str, str]],
    average_difficulty: int,
    num_questions: int,
    topics_to_focus_on: List[str]
) -> Optional[List[QuizQuestion]]:
    try:
        relationship_str = "\n".join([f"{relationship['source']} {relationship['type']} {relationship['target']}" for relationship in relationships])
        raw_text_str = "\n".join([f"Chunk ID: {raw_text['id']}, Text: {raw_text['text']}" for raw_text in raw_texts])
        topics_to_focus_on_str = ", ".join(topics_to_focus_on) if topics_to_focus_on else "Any"

        print(f"relationship_str: {relationship_str}")
        print(f"raw_text_str: {raw_text_str}")

        extraction_chain = setup_llm(
            relationship_str=relationship_str, 
            raw_text_str=raw_text_str, 
            average_difficulty=average_difficulty, 
            num_questions=num_questions,
            topics_to_focus_on=topics_to_focus_on_str
        )

        result = extraction_chain.invoke({})
        
        return result.questions
    except Exception as e:
        logger.error(f"Error generating quiz questions: {str(e)}")
        raise

class QuizService():
    validSpecifiers = ['courseId', 'noteId']

    @staticmethod
    def generate_quiz(topics=[],
                      courseId=None,
                      userId=None,
                      quizId=None,
                      noteId=None,
                      difficulty=None,
                      numQuestions=None,
                      specifierParam=None
                      ):
        
        id = noteId if specifierParam == 'noteId' else courseId

        topic_graph = GraphQueryService.get_topic_graph(
            id=id,
            specifierParam=specifierParam,
            topics=topics,
            num_communities=DEFAULT_COMMUNITIES
            )
    
        if topic_graph is None:
            logging.error(f"Failed to generate topic graph for quiz {quizId}")
            return None
        
        logging.info(f"Generated topic graph for quiz: {quizId}, topics: {topics}")
        
        questionIds = []
        
        for _ in range(numQuestions):
            question = SupabaseService.add_quiz_question(quizId=quizId)

            if len(question) == 0:
                logging.error(f"Failed to add question for quiz {quizId}")
                return None
            
            questionIds.append(question[0]['id'])
        
        logging.info(f"Generated placeholder quiz questions for quiz {quizId}")

        questions = QuizService.generate_quiz_questions(
            topic_graph=topic_graph,
            difficulty=difficulty,
            numQuestions=numQuestions,
            topics_to_focus_on=topics
            )
        
        pprint(questions)

        if questions is None or len(questions) == 0:
            return None

        formatted_questions = []
        for i, question in enumerate(questions):
            formatted_questions.append(
                {
                    'questionId': questionIds[i],
                    'quizId': quizId,
                    'courseId': courseId,
                    'noteId': noteId,
                    'userId': userId,
                    'question': question.question,
                    'difficulty': question.difficulty,
                    'answers': [{'label': answer.answer, 'correct': answer.correct, 'explanation': answer.explanation} for answer in question.answers],
                    'chunkIds': question.chunkIds,
                    'topics': question.topics
                }
            )
        
        GraphCreationService.insert_quiz_question(questions=formatted_questions)

        logging.info(f"Generated quiz questions for quiz {quizId}")
    
    @staticmethod
    def generate_quiz_questions(
        topic_graph, 
        difficulty=None,
        numQuestions=None,
        topics_to_focus_on=''
    ):
        try:
            return generate_quiz_questions(
                relationships=topic_graph['conceptRels'],
                raw_texts=topic_graph['chunks'],
                average_difficulty=difficulty,
                num_questions=numQuestions,
                topics_to_focus_on=topics_to_focus_on
            )
        except Exception as e:
            logging.exception(f"Error generating quiz questions: {str(e)}")
            return None
