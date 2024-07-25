import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from typing import Dict, List, Optional
from tiktoken import encoding_for_model
from uuid import uuid4

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from retry import retry

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.HelperService import HelperService
from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import GPT_35_TURBO_MODEL, GPT_4O_MODEL, GPT_4O_MINI
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.GraphCreationService import GraphCreationService

class Summary(BaseModel):
    summary: str = Field(
        description="A markdown formatted summary of the given relationships and raw text chunks, 3-4 paragraphs long."
    )

def setup_llm(
    main_concept: str,
    related_concepts_str: str,
    chunks_str: str,
):
    system_prompt = """
    You are an advanced Markdown formatted summarization system. Your task is to generate a focused, extended sub-summary that delves deeply into a single main concept.

    ## Key Guidelines:
    1. Focus exclusively on the main concept, only mentioning related concepts in direct relation to the main concept.
    2. Create a sub-summary equivalent to 6-8 paragraphs in length, using markdown formatting for readability.
    3. Start immediately with content relevant to the main concept. No introduction or conclusion.
    4. Use provided information to support your summary with specific details and examples.
    5. Utilize markdown features: headings, lists, bold/italic text, blockquotes, code blocks, and tables as appropriate.
    6. IMPORTANT: Cite individual chunks using ONLY this format: [Chunk Name](Chunk UUID)
       Examples:
       - [Introduction to AI](550e8400-e29b-41d4-a716-446655440000)
       - [Machine Learning Basics](6ba7b810-9dad-11d1-80b4-00c04fd430c8)
       - [Neural Networks](6ba7b811-9dad-11d1-80b4-00c04fd430c8)

    Always start with a level 2 heading of the main concept and end with relevant, substantive information.
    """
    
    user_template = f"""
    Generate a focused, extended sub-summary based on:

    Main Concept: {main_concept}
    Related Concepts: {related_concepts_str}

    Text Information:
    {chunks_str}

    Your markdown-formatted sub-summary should:
    - Start with a level 2 heading of the main concept
    - Be equivalent to 6-8 paragraphs, using extensive markdown formatting
    - Focus exclusively on the main concept
    - Incorporate relevant information from the provided text
    - Use markdown features to enhance readability and structure
    - End with substantive information about the main concept

    #CRITICAL:
    - ALWAYS cite chunks using ONLY this format: [Chunk Name](Chunk UUID)
    - NO conclusions or summaries at the end
    - Failure to cite correctly or adding a conclusion will result in immediate termination
    """

    extraction_llm = get_llm(GPT_4O_MINI)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

def count_tokens(text: str) -> int:
    enc = encoding_for_model("gpt-3.5-turbo")
    return len(enc.encode(text))

@retry(tries=3, delay=2)
def generate_summary(
    main_concept: str,
    main_concept_uuid: str,
    related_concepts: List[Dict[str, str]],
    chunks: List[Dict[str, str]],
) -> Optional[Summary]:
    try:
        logging.info(f"Generating summary for Main Concept: {main_concept}")
        related_concepts_str = ", ".join([concept['id'] for concept in related_concepts])
        chunks_str = "\n".join([f"Chunk Name: {chunk['document_name']}, Chunk ID: {chunk['id']}, Chunk Text: {chunk['text']}" for chunk in chunks])

        logging.info(f"Chunks: {chunks_str}")

        extraction_chain = setup_llm(
            main_concept=main_concept, 
            related_concepts_str=related_concepts_str,
            chunks_str=chunks_str
        )

        result = extraction_chain.invoke({})
        
        logging.info(f"Generated summary for {main_concept}. Token count: {result.dict()['usage_metadata']['total_tokens']}")

        return {
            'content': result.dict()['content'],
            'concept': main_concept,
            'concept_uuid': main_concept_uuid
        }
    except Exception as e:
        logging.error(f"Error generating summary: {str(e)}")
        raise

class SummaryService():
    @staticmethod
    def get_individual_summary(
        main_concept: str,
        main_concept_uuid: str,
        related_concepts: List[Dict[str, str]],
        chunks: List[Dict[str, str]],
    ):
        logging.info(f"Generating individual summary for {main_concept}")
        return generate_summary(
            main_concept=main_concept,
            related_concepts=related_concepts,
            main_concept_uuid=main_concept_uuid,
            chunks=chunks
        )

    @staticmethod
    def generate_note_summary(
        userId: str, 
        courseId: str,
        specifierParam: str,
        noteId: str = None,
        topics: List[str] = []
        ):

        if (
            not HelperService.validate_uuid4(noteId)
            and (not HelperService.validate_uuid4(courseId) and len(topics) == 0)
        ): 
            logging.error(f"Must have noteId or courseId and at least one topic")
            return None

        id = noteId if specifierParam == 'noteId' else courseId

        importance_graph = GraphQueryService.get_importance_graph_by_param(param=specifierParam, id=id)

        if importance_graph is None:
            logging.error(f"No importance graph found for {specifierParam}: {id}")
            return None

        futures = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            for graph in importance_graph:
                if graph is not None:
                    futures.append(
                        executor.submit(
                            SummaryService.get_individual_summary,
                            main_concept=graph['conceptId'],
                            main_concept_uuid=graph['conceptUuid'],
                            related_concepts=graph['relatedConcepts'],
                            chunks=graph['topChunks']
                        ))
        
            for future in concurrent.futures.as_completed(futures):
                try:
                    summary = future.result()

                    SupabaseService.update_note(noteId, 'summaryStatus', str(uuid4()))

                    # modified_content = SummaryService.inject_topic_links(summary['content'])

                    summary = {
                        'content': summary['content'],
                        'concept': summary['concept'],
                        'userId': userId,
                        'courseId': courseId,
                        'noteId': noteId if noteId is not None else 'None',
                        'topicId': summary['concept_uuid']
                    }

                    GraphCreationService.insert_summaries([summary])
                    logging.info(f"Generated summary")
                except Exception as e:
                    logging.error(f"Error generating summary: {str(e)}")
                    raise
        
        SupabaseService.update_note(noteId, 'summaryStatus', 'complete')
            
    @staticmethod
    def generate_topic_summary(
        userId: str,
        courseId: str,
        topicId: str,
    ):
        logging.info(f"Generating topic summary for {topicId}")

        topic_graph = GraphQueryService.get_topic_graph_for_topic_uuid(topic_uuid=topicId)[0]['result']

        if topic_graph is None:
            return None
        
        summaryId = SupabaseService.add_summary(topicId=topicId)[0]['id']
        
        summary = SummaryService.get_individual_summary(
            main_concept=topic_graph['start_concept']['id'],
            main_concept_uuid=topic_graph['start_concept']['uuid'],
            related_concepts=topic_graph['related_concepts'],
            chunks=topic_graph['related_chunks']
        )

        if summary is None:
            return None
        
        summary_final = {
            'summaryId': summaryId,
            'content': summary['content'],
            'concept': topic_graph['start_concept']['id'],
            'userId': userId,
            'courseId': courseId,
            'topicId': topicId,
            'noteId': 'None'
        }

        GraphCreationService.insert_summaries([summary_final])

        SupabaseService.update_summary(summaryId, 'status', 'complete')

    # @staticmethod
    # def inject_topic_links(content: str) -> str:
    #     topics = 