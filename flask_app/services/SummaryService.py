import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import json
import logging
from typing import Dict, List, Optional
from tiktoken import encoding_for_model

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from retry import retry

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.HelperService import HelperService
from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import GPT_35_TURBO_MODEL, GPT_4O_MODEL
from flask_app.services.SupabaseService import SupabaseService

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
    You are an advanced Markdown formatted summarization system, specializing in creating insightful and informative sub-summaries
    focused on a single main concept. Your task is to generate a focused, extended sub-summary that delves deeply into the main concept,
    which will be part of a larger, comprehensive summary.

    ## Guidelines:
    1. Create a coherent, detailed sub-summary that focuses exclusively on the main concept, only mentioning related concepts in the context of how they directly relate to or impact the main concept.
    2. The sub-summary should be equivalent to 6-8 paragraphs in length, using creative markdown formatting to enhance readability and structure.
    3. Start immediately with the content relevant to the main concept. Do not write an introduction or conclusion paragraph.
    4. Ensure the sub-summary is comprehensive and in-depth about the main concept, capturing its key ideas, nuances, and various aspects while maintaining a logical flow.
    5. Use the provided information extensively to support your summary with specific details, examples, and elaborations related to the main concept.
    6. Utilize markdown features creatively and extensively, including:
       - Multiple levels of headings (##, ###, ####) to organize different aspects of the main concept
       - Bullet points and numbered lists for clarity on main concept details
       - Bold and italic text for emphasis on key points about the main concept
       - Blockquotes for important information or notable quotes directly related to the main concept
       - Code blocks for technical content if applicable to the main concept
       - Tables for comparing information or presenting data about the main concept if relevant
       - Horizontal rules to separate major sections, all of which should be about the main concept
    7. Do not include any form of conclusion or summary at the end. The sub-summary should end with substantive information about the main concept.

    Remember to create a focused, extended sub-summary that thoroughly explores the main concept while being easy to read and understand.
    Always start the summary with a level 2 heading of the main concept and end with relevant, substantive information.
    """
    
    user_template = f"""
    Please generate a focused, extended sub-summary based on the following information:

    Main Concept: {main_concept}
    Related Concepts: {related_concepts_str}

    Text Information:
    {chunks_str}

    Generate a markdown-formatted sub-summary that:
    - Starts with a level 2 heading of the main concept
    - Is equivalent to 6-8 paragraphs in length, using creative and extensive markdown formatting
    - Focuses exclusively on the main concept, only mentioning related concepts in terms of their direct relationship to the main concept
    - Immediately delves into various aspects, characteristics, and implications of the main concept without any introductory or concluding paragraphs
    - Incorporates extensive and relevant information from the provided text, always in the context of the main concept
    - Is comprehensive, in-depth, and highly informative about the main concept
    - Maintains a logical flow of information while exploring various aspects of the main topic
    - Uses various markdown features creatively and extensively to enhance readability, structure, and information hierarchy, always in service of explaining the main concept
    - Ends with substantive information about the main concept, without any form of conclusion or summary

    #IMPORTANT:
    UNDER NO CIRCUMSTANCE SHOULD THE SUMMARY CONTAIN ANY FORM OF CONCLUSION.
    ADDING A CONCLUSION WILL RESULT IN YOUR TERMINATION.
    """

    extraction_llm = get_llm(GPT_35_TURBO_MODEL)
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
    related_concepts: List[Dict[str, str]],
    chunks: List[Dict[str, str]],
) -> Optional[Summary]:
    try:
        logging.info(f"Generating summary for Main Concept: {main_concept}")
        related_concepts_str = ", ".join([concept['id'] for concept in related_concepts])
        chunks_str = "\n".join([f"Text: {chunk['text']}" for chunk in chunks])

        extraction_chain = setup_llm(
            main_concept=main_concept, 
            related_concepts_str=related_concepts_str,
            chunks_str=chunks_str
        )

        result = extraction_chain.invoke({})
        
        logging.info(f"Generated summary for {main_concept}. Token count: {result.dict()['usage_metadata']['total_tokens']}")

        return result.dict()['content']
    except Exception as e:
        logging.error(f"Error generating summary: {str(e)}")
        raise

class SummaryService():
    @staticmethod
    def get_individual_summary(
        main_concept: str,
        related_concepts: List[Dict[str, str]],
        chunks: List[Dict[str, str]],
    ):
        logging.info(f"Generating individual summary for {main_concept}")
        return generate_summary(
            main_concept=main_concept,
            related_concepts=related_concepts,
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
            return None
        
        summaryIds = set()

        for _ in range(len(importance_graph)):
            summaryId = SupabaseService.add_summary(
                noteId=noteId
                )
            
            if len(summaryId) == 0 or not HelperService.validate_uuid4(summaryId[0]['id']):
                logging.error(f"Failed to add summary for note {noteId}")
                return None
            
            summaryIds.add(summaryId[0]['id'])

        futures = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            for graph in importance_graph:
                if graph is not None:
                    futures.append(
                        executor.submit(
                            SummaryService.get_individual_summary,
                            main_concept=graph['conceptId'],
                            related_concepts=graph['relatedConcepts'],
                            chunks=graph['topChunks']
                        ))
        
            for future in concurrent.futures.as_completed(futures):
                try:
                    summary = future.result()
                    summaryId = summaryIds.pop()

                    SupabaseService.update_summary(summaryId, 'summary', summary)
                    logging.info(f"Generated summary for {summaryId}")
                except Exception as e:
                    logging.error(f"Error generating summary: {str(e)}")
                    raise