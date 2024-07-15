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

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from langchain.prompts import ChatPromptTemplate
from retry import retry
import logging

class Summary(BaseModel):
    summary: str = Field(
        description="A markdown formatted summary of the given relationships and raw text chunks"
    )

def setup_llm(
        relationship_str, 
        raw_text_str,
):
    system_prompt = """
    You are an advanced summarization system, specializing in creating insightful and informative summaries
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

    extraction_llm = get_llm(model_name="gpt-3.5-turbo-0125").with_structured_output(Summary)
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
        relationships: List[Dict[str, str]],
        raw_texts: List[Dict[str, str]],
    ):
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

        communities = GraphQueryService.get_communities_for_param(
            param=specifierParam, 
            id=id, 
            topics=topics,
            num_communities=None
            )
        
        if len(communities) == 0:
            return None

        topic_graphs = []
        if specifierParam == 'noteId':
            for community in communities:
                topic_graphs.append(GraphQueryService.get_topic_graph_for_communities(
                    param=specifierParam, 
                    id=id, 
                    communities=[community]
                    ))
        else:
            topic_graphs.append(GraphQueryService.get_topic_graph_for_communities(
                param=specifierParam, 
                id=id, 
                communities=communities
                ))

        summaries = []
        futures=[]
        with ThreadPoolExecutor(max_workers=10) as executor:
            for graph in topic_graphs:
                futures.append(
                    executor.submit(
                        SummaryService.get_inidividual_summary,
                        relationships=graph['conceptRels'],
                        raw_texts=graph['chunks']
                    ))
        
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                summary = future.result()
                summaries.append(summary)   

        print(f"summaries: {summaries}")
        
        return summaries
