import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Dict, List, Optional

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from retry import retry

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.src.shared.common_fn import get_llm
from flask_app.constants import GPT_35_TURBO_MODEL

class Summary(BaseModel):
    summary: str = Field(
        description="A markdown formatted summary of the given relationships and raw text chunks."
    )
    oneLineSummary: str = Field(
        description="A one line summary of what was talkd about in the full length summary."
    )

def setup_llm(
    relationship_str, 
    raw_text_str,
):
    system_prompt = """
    You are an advanced Markdown formatted summarization system, specializing in creating insightful and informative summaries
    based on provided information. Your task is to generate a summary tailored to the given relationships and raw text chunks.

    Input:
    - A list of relationships between entities that contains the following fields: SourceName, SourceUUID, RelType, TargetName, TargetUUID
    - A list of raw text chunks that contains the following fields: ChunkId, ChunkName, Text

    ## Guidelines:
    1. Create a coherent summary that incorporates information from both the relationships and raw text chunks.
    2. Use markdown formatting for the summary.
    3. Include references to concepts and chunks in the summary using the following format:
       (Concept name or Chunk Name)[Concept UUID or Chunk UUID]
    4. Ensure the summary is comprehensive yet concise, capturing the main ideas and connections.
    5. Maintain a logical flow of information in the summary.

    Remember to create a balanced summary that effectively represents the provided information while being easy to read and understand.
    """
    
    user_template = f"""
    Please generate a summary based on the following information:

    1. Entity Relationships: {relationship_str}

    2. Raw Text Chunks: {raw_text_str}

    Generate a summary that:
    - Incorporates information from both the relationships and raw text chunks
    - Uses markdown formatting
    - Includes references to concepts and chunks using the format: (Concept Name or Chunk Name)[Concept UUID or Chunk UUID]
    - Is comprehensive and informative
    - Maintains a logical flow of information

    Please provide the summary in the format specified in the Summary model.
    """

    extraction_llm = get_llm(GPT_35_TURBO_MODEL).with_structured_output(Summary)
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", user_template),
    ])
    
    return extraction_prompt | extraction_llm

@retry(tries=3, delay=2)
def generate_summary(
    relationships: List[Dict[str, str]],
    raw_texts: List[Dict[str, str]]
) -> Optional[Summary]:
    try:
        relationship_str = "\n".join([f"""SourceName: {relationship['source']}, 
                                      SourceUUID: {relationship['sourceUUID']}, 
                                      RelType: {relationship['type']}, 
                                      TargetName: {relationship['target']},
                                      TargetUUID: {relationship['targetUUID']}"""
                                      for relationship in relationships])
        raw_text_str = "\n".join([f"""ChunkId: {raw_text['id']}, 
                                  ChunkName: {raw_text['document_name']}, 
                                  Text: {raw_text['text']}""" 
                                  for raw_text in raw_texts])

        extraction_chain = setup_llm(
            relationship_str=relationship_str, 
            raw_text_str=raw_text_str
        )

        result = extraction_chain.invoke({})
        
        return result
    except Exception as e:
        logging.error(f"Error generating summary: {str(e)}")
        raise

class SummaryService():
    @staticmethod
    def get_inidividual_summary(
        main_concept: str,
        related_concepts: List[str],
        chunks: List[Dict[str, str]],
    ):
        print(f"main_concept: {main_concept}, related_concepts: {related_concepts}, chunks: {chunks}")

        return None

        return generate_summary(
            relationships=relationships,
            raw_texts=raw_texts
        )

    @staticmethod
    def generate_summary(
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
            logging.error(f"Must have noeId or courseId and at least one topic")
            return None

        id = noteId if specifierParam == 'noteId' else courseId

        importance_graph = GraphQueryService.get_importance_graph_by_param(param=specifierParam, id=id)

        if importance_graph is None:
            return None

        summaries = []
        futures=[]
        with ThreadPoolExecutor(max_workers=10) as executor:
            for graph in importance_graph:
                if graph is not None:
                    futures.append(
                        executor.submit(
                            SummaryService.get_inidividual_summary,
                            main_concept=graph['conceptId'],
                            related_concepts=graph['relatedConcepts'],
                            chunks=graph['topChunks']
                        ))
        
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                summary = future.result()
                summaries.append(summary)   

        print(f"summaries: {summaries}")
        
        return summaries
