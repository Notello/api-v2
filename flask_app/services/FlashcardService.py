import logging
from typing import Dict, List, Optional

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.RatelimitService import RatelimitService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.GraphCreationService import GraphCreationService

from flask_app.constants import COURSEID, NOTEID, FLASHCARD, GPT_4O_MINI
from flask_app.src.shared.common_fn import get_llm

class Flashcard(BaseModel):
    topic: str = Field(description="The name of the topic for the flashcard")
    uuid: str = Field(description="The UUID of the topic for the flashcard")
    description: str = Field(description="The description of the topic for the flashcard")

class FlashcardResult(BaseModel):
    flashcards: List[Flashcard] = Field(description="A list of flashcards")

def setup_llm(
    topic_str: str,
    chunks_str: str,
):
    system_prompt = """
    You are a context aware flashcard generator, specializing in creating flashcards for all topics given to you.
    Your task if to generate a flashcard for each topic given to you, based on the provided text chunks.

    For each topic you will generate a flashcard with the following values:
    - topic: The name of the topic
    - uuid: The UUID of the topic
    - description: A description of the topic that is relevant to the provided text chunks
    """
    
    user_template = f"""
    Please generate flashcards for the following topics and text chunks:

    Topics:
    {topic_str}

    Text Chunks:
    {chunks_str}
    """

    extraction_llm = get_llm(GPT_4O_MINI).with_structured_output(FlashcardResult)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

def generate_flashcards(
    topics,
    chunks,
) -> Optional[List[Dict]]:
    try:
        logging.info(f"Generating flashcards for topics: {topics}")
        chunks_str = "\n".join([f"Chunk ID: {chunk['id']}, Text: {chunk['text']}" for chunk in chunks])
        topics_str = "\n".join([f"Topic Name: {topic['id']}, Topic UUID: {topic['uuid']}" for topic in topics])

        extraction_chain = setup_llm(
            topic_str=topics_str,
            chunks_str=chunks_str
        )

        result = extraction_chain.invoke({})
        
        return result
    except Exception as e:
        logging.error(f"Error generating quiz questions: {str(e)}")
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

    @staticmethod
    def create_flashcards(
            courseId: str, 
            noteId: str, 
            userId: str,
            param: str,
            specifierId: str,
            flashcardId: str
        ):
        batch_size = 20

        ratelimitId = RatelimitService.add_rate_limit(userId=userId, type=FLASHCARD, value=batch_size)
        try:
            if ratelimitId is None:
                return None
        
            context = GraphQueryService.get_new_topic_flashcard_pairs_for_param(
                param=param,
                id=specifierId,
                userId=userId,
                num_pairs=batch_size
            )

            logging.info(f"Context: {context}")

            topic_pairs_to_generate = {pair['conceptUuid']: pair for pair in context['concept_pairs'] if not pair["hasFlashcard"]}
            final_map = {pair['conceptUuid']: pair for pair in context['concept_pairs'] if pair["hasFlashcard"]}
            related_chunks = context['relatedChunks']
            has_more_concepts = context['hasMoreConcepts']
            cards = []

            logging.info(f"Topic pairs to generate: {topic_pairs_to_generate}")
            logging.info(f"Final map: {final_map}")

            if len(topic_pairs_to_generate) > 0:
                flashcards: FlashcardResult = generate_flashcards(
                    topics=[{
                        'id': topic_pairs_to_generate[topic]['conceptId'],
                        'uuid': topic_pairs_to_generate[topic]['conceptUuid']
                    } for topic in topic_pairs_to_generate],
                    chunks=related_chunks
                )

                if flashcards is None:
                    return None
                
                logging.info(f"Flashcards: {flashcards}")

                for flashcard in flashcards.flashcards:
                    if flashcard.uuid in topic_pairs_to_generate:
                        final_map[flashcard.uuid] = topic_pairs_to_generate.get(flashcard.uuid)
                        final_map[flashcard.uuid]['flashcardLabel'] = flashcard.description
                        cards.append(final_map[flashcard.uuid])

            GraphCreationService.insert_flashcards(flashcards=cards, noteId=noteId, courseId=courseId, userId=userId)
            
        except Exception as e:
            logging.error(f"Error generating flashcards: {str(e)}")
            SupabaseService.delete_rate_limit(rateLimitId=ratelimitId)
            return None