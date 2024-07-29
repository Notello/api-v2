import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import re
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
from flask_app.constants import COURSEID, GPT_35_TURBO_MODEL, GPT_4O_MODEL, GPT_4O_MINI, LLAMA_405_MODEL, LLAMA_70B_MODEL, NOTEID, USERID
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
    You are an advanced citation focused Markdown formatted summarization system. Your task is to generate a focused, extended sub-summary that delves deeply into a single main concept and cites as many related concepts as possible.

    ## Key Guidelines:
    1. Focus exclusively on the main concept, mentioning as many ##RELATED CONCEPTS## as possible in direct relation to the main concept.
    2. Create a sub-summary equivalent to 6-8 paragraphs in length, using markdown formatting for readability.
    3. Start immediately with content relevant to the main concept. No introduction or conclusion.
    4. Use provided chunks to support your summary with specific details and examples.
    5. Utilize markdown features: headings, lists, bold/italic text, blockquotes, code blocks, and tables as appropriate.
    6. Prefer to use code blocks to highlight important information.

    ## CRITICAL: Concept and Chunk Citation Guidelines
    2. ALWAYS cite ##RELATED CONCEPTS## using this format: [Concept Name](Concept UUID)
    3. ALWAYS cite chunks using this format: [Chunk Name](Chunk UUID)

    Examples:
    - Related Concept: [Machine Learning](6ba7b810-9dad-11d1-80b4-00c04fd430c8)
    - Chunk: [Introduction to AI](6ba7b811-9dad-11d1-80b4-00c04fd430c8)

    IMPORTANT: 
    - Cite the main concept and ##RELATED CONCEPTS## as frequently as possible without disrupting readability.
    - Aim to include ALL ##RELATED CONCEPTS## at least once in your summary.
    - Failure to cite correctly or adding a conclusion will result in immediate termination.

    Always start with a level 2 heading of the main concept and end with relevant, substantive information.
    """
    
    user_template = f"""
    Generate a focused, extended sub-summary based on:

    Main Concept: {main_concept}
    ##RELATED CONCEPTS##: {related_concepts_str}

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
    - ALWAYS cite ##RELATED CONCEPTS## using this format: [Concept Name](Concept UUID)
    - ALWAYS cite chunks using this format: [Chunk Name](Chunk UUID)
    - Include as many ##RELATED CONCEPTS## as possible, aiming to reference ALL of them at least once
    - Cite concepts and chunks as frequently as possible without disrupting readability
    - Never say the word "Chunk" or "Chunks" in your summary, simply refer to the document name
    - NO conclusions or summaries at the end
    - Failure to cite correctly or adding a conclusion will result in immediate termination

    Remember to reference the main concept and ##RELATED CONCEPTS## using their respective UUIDs whenever mentioned.
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
        related_concepts_str = ", ".join([f"Concept Name: {concept['id']}, Concept UUID: {concept['uuid']}" for concept in related_concepts])
        chunks_str = "\n".join([f"Chunk Name: {chunk['document_name']}, Chunk UUID: {chunk['id']}, Chunk Text: {chunk['text']}" for chunk in chunks])
        chunks_map = {chunk['id']: 
            {
            'document_name': chunk['document_name'],
            'offset': chunk['offset'],
            'noteId': chunk['noteId']
            } 
            for chunk in chunks}

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
            'concept_uuid': main_concept_uuid,
            'chunks_map': chunks_map
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

        id = noteId if specifierParam == NOTEID else courseId

        importance_graph = GraphQueryService.get_importance_graph_by_param(param=specifierParam, id=id)
        topics = GraphQueryService.get_topics_for_param(param=COURSEID, id=courseId)

        if importance_graph is None or len(importance_graph) == 0:
            logging.error(f"No importance graph found for {specifierParam}: {id}")
            return None
        
        futures = []

        print(importance_graph)

        with ThreadPoolExecutor(max_workers=10) as executor:
            for graph in importance_graph:
                if graph is not None and 'conceptId' in graph and 'relatedConcepts' in graph and 'topChunks' in graph:
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

                    modified_content = SummaryService.inject_topic_links(
                        summary['content'], 
                        topics=topics, 
                        chunks_map=summary['chunks_map'],
                        courseId=courseId
                        )

                    summary = {
                        'content': modified_content,
                        'concept': summary['concept'],
                        USERID: userId,
                        COURSEID: courseId,
                        NOTEID: noteId if noteId is not None else 'None',
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
        logging.info(f"Generating topic summary for topic: {topicId}")

        topic_graph = GraphQueryService.get_topic_graph_for_topic_uuid(topic_uuid=topicId)

        if topic_graph is None or len(topic_graph) == 0:
            logging.error(f"No topic graph found for {topicId}, topic_graph: {topic_graph}")
            return None

        topics = GraphQueryService.get_topics_for_param(param=COURSEID, id=courseId)

        if topic_graph is None:
            return None
        
        print(topic_graph)
        
        summaryId = SupabaseService.add_summary(topicId=topicId)[0]['id']

        graph = topic_graph[0]['result']
        
        summary = SummaryService.get_individual_summary(
            main_concept=graph['start_concept']['id'],
            main_concept_uuid=graph['start_concept']['uuid'],
            related_concepts=graph['related_concepts'],
            chunks=graph['related_chunks']
        )

        logging.info(f"Generated summary for topic {topicId}")

        if summary is None:
            return None
        
        logging.info(f"All topics: {topics}")
        
        summary_final = SummaryService.inject_topic_links(
            summary['content'], 
            topics=topics, 
            chunks_map=summary['chunks_map'],
            courseId=courseId,
            )
        
        summary_final = {
            'summaryId': summaryId,
            'content': summary_final,
            'concept': graph['start_concept']['id'],
            USERID: userId,
            COURSEID: courseId,
            'topicId': topicId,
            NOTEID: 'None'
        }

        GraphCreationService.insert_summaries([summary_final])

        SupabaseService.update_summary(summaryId, 'status', 'complete')

    @staticmethod
    def inject_topic_links(
        content: str,
        topics: List[Dict[str, str]],
        chunks_map: Dict[str, str],
        courseId: str
    ) -> str:
        logging.info(f"Content before topic injection: {content}")
        logging.info(f"Topics: {topics}")
        logging.info(f"Chunks Map: {chunks_map}")
        
        # Sort topics by length of conceptId in descending order
        # This ensures longer matches are replaced first
        sorted_topics = sorted(topics, key=lambda x: len(x['conceptId']), reverse=True)
        
        def normalize_text(text: str):
            return re.sub(r'[-_/\s]', '', text.lower())

        # Step 1: Replace chunk references
        def replace_chunk_reference(match: re.Match):
            link_text, link_url = match.groups()
            if link_url in chunks_map:
                document_name = chunks_map[link_url]['document_name']
                noteId = chunks_map[link_url]['noteId']
                offset = chunks_map[link_url]['offset']
                return f"[{document_name}](/course/{courseId}/note/{noteId}?offset={offset})"
            return match.group(0)

        content = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', replace_chunk_reference, content)

        # Step 2: Replace concept names
        def replace_concept(match: re.Match):
            word = match.group(0)
            normalized_word = normalize_text(word)
            for topic in sorted_topics:
                if normalize_text(topic['conceptId']) == normalized_word:
                    return f"[{word}](/course/{courseId}/topic/{topic['conceptUuid']})"
            return word

        # Split content into parts: inside links and outside links
        parts = re.split(r'(\[[^\]]+\]\([^\)]+\))', content)
        
        for i in range(0, len(parts), 2):
            # Only process parts outside of links
            parts[i] = re.sub(r'\b[\w-]+\b', replace_concept, parts[i])

        content = ''.join(parts)

        # Step 3: Process remaining concept links injected by the LLM
        def process_remaining_concepts(match: re.Match):
            concept_name, uuid = match.groups()
            if uuid not in chunks_map:  # Ensure it's not a chunk reference
                return f"[{concept_name}](/course/{courseId}/topic/{uuid})"
            return match.group(0)

        content = re.sub(r'\[([^\]]+)\]\(([a-f0-9-]+)\)', process_remaining_concepts, content)

        logging.info(f"Injected topic links into content: {content}")

        return content