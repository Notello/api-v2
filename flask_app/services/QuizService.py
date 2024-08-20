import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Dict, List, Optional
import uuid
import numpy as np

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.GraphCreationService import GraphCreationService
from flask_app.services.RatelimitService import RatelimitService
from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import COURSEID, GPT_4O_MINI, NOTEID, QUIZ, USERID

logger = logging.getLogger(__name__)

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
        source_str, 
        target_str,
        relationship_type_str,
        chunks_str,
        difficulty_str,
        num_questions
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

def generate_quiz_questions(
    source: str,
    target: str,
    relationship_type: str,
    chunks: List[Dict[str, str]],
    difficulty: int,
    num_questions: int
) -> Optional[List[Dict]]:
    try:
        logging.info(f"Generating quiz questions for source: {source}, target: {target}, relationship type: {relationship_type}, chunks: {len(chunks)}, difficulty: {difficulty}, num_questions: {num_questions}")
        chunks_str = "\n".join([f"Chunk ID: {chunk['id']}, Text: {chunk['text']}" for chunk in chunks])

        extraction_chain = setup_llm(
            source_str=source,
            target_str=target,
            relationship_type_str=relationship_type,
            chunks_str=chunks_str,
            difficulty_str=difficulty,
            num_questions=num_questions
        )

        results = extraction_chain.invoke({})

        output = [{"question": question, "topics": [source, target]} for question in results.questions]
        
        return output
    except Exception as e:
        logger.error(f"Error generating quiz questions: {str(e)}")
        raise

class QuizService():
    validSpecifiers = [COURSEID, NOTEID]

    @staticmethod
    def generate_quiz(topics=[],
                      courseId=None,
                      userId=None,
                      quizId=None,
                      noteId=None,
                      difficulty=None,
                      numQuestions=None,
                      specifierParam=None,
                      ):
        
        rateLimitId = RatelimitService.add_rate_limit(userId, QUIZ, numQuestions)

        try:
            id = noteId if specifierParam == NOTEID else courseId

            topic_graph = GraphQueryService.get_topic_graph(
                id=id,
                param=specifierParam,
                topics=topics,
                num_rels=numQuestions
                )
            
            if topic_graph is None:
                logging.error(f"Failed to generate topic graph for quiz {quizId}")
                return None
            
            logging.info(f"Generated topic graph for quiz: {quizId}, topics: {topics}")

            results = QuizService.generate_quiz_questions(
                topic_graph=topic_graph,
                difficulty=difficulty,
                numQuestions=numQuestions
                )
            

            if results is None or len(results) == 0:
                return None

            formatted_questions = []

            for question in results:
                formatted_questions.append(
                    {
                        'questionId': str(uuid.uuid4()),
                        'quizId': [quizId],
                        COURSEID: [courseId],
                        NOTEID: [noteId],
                        USERID: [userId],
                        'question': question['question'].question,
                        'difficulty': question['question'].difficulty,
                        'answers': [{'label': answer.answer, 'correct': answer.correct, 'explanation': answer.explanation} for answer in question['question'].answers],
                        'chunkIds': question['question'].chunkIds,
                        'topics': question['topics']
                    }
                )
            
            GraphCreationService.insert_quiz_question(questions=formatted_questions)

            SupabaseService.update_quiz(quizId=quizId, key='status', value='complete')

            logging.info(f"Generated quiz questions for quiz {quizId}")
        except Exception as e:
            logging.exception(f"Error generating quiz: {str(e)}")
            SupabaseService.update_quiz(quizId=quizId, key='status', value='error')
            RatelimitService.remove_rate_limit(rateLimitId)
            return None
    
    @staticmethod
    def generate_quiz_questions(
        topic_graph, 
        difficulty=None,
        numQuestions=None,
    ):
        futures = []
        questions = []

        numQuestionsList = [0 for _ in range(len(topic_graph))]
        for i in range(numQuestions):
            numQuestionsList[i % len(topic_graph)] += 1

        # Generate a normal distribution around the difficulty parameter
        difficultyList = np.random.normal(difficulty, 0.5, len(topic_graph))
        difficultyList = np.clip(difficultyList, 1, 5)  # Ensure difficulties are between 1 and 5
        difficultyList = [round(d) for d in difficultyList]  # Round to nearest integer

        print(f"LEN OF TOPIC GRAPH: {len(topic_graph)}")
        with ThreadPoolExecutor(max_workers=10) as executor:
            for i, result_dict in enumerate(topic_graph):
                if result_dict is not None and numQuestionsList[i] > 0:
                    result = result_dict['result']
                    futures.append(
                        executor.submit(
                            generate_quiz_questions,
                            source=result['source'],
                            target=result['target'],
                            relationship_type=result['type'],
                            chunks=result['chunks'],
                            difficulty=difficultyList[i],
                            num_questions=numQuestionsList[i]
                        ))
        
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    questions.extend(result)
                    logging.info(f"Generated {len(result)} questions for topic pair")
                except Exception as e:
                    logging.error(f"Error generating questions: {str(e)}")
                    raise

        return questions