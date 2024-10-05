from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import logging
from datetime import datetime
import logging
from uuid import uuid4

from flask_app.src.make_relationships import create_relation_between_chunks, merge_relationship_between_chunk_and_entities, update_chunk_embedding
from flask_app.src.shared.common_fn import clean_nodes
from flask_app.src.openAI_llm import get_graph_from_OpenAI
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.NodeUpdateService import NodeUpdateService
from flask_app.services.SupaGraphService import SupaGraphService
from flask_app.constants import NOTEID

def processing_source(
      fileName: str, 
      chunks, 
      userId,
      courseId,
      noteId,
      summary
      ):
        
    logging.info("Break down file into chunks")

    SupabaseService.update_note(noteId, 'graphStatus', '1')
    
    logging.info('Update the status as Processing')

    futures = []
    nodes_data = []

    logging.info(f"Total chunks: {len(chunks)}")

    try:
        with ThreadPoolExecutor(max_workers=50) as executor:
            for i, chunk in enumerate(chunks):
                futures.append(
                    executor.submit(
                        process_chunks,
                        chunk=chunk,
                        noteId=noteId,
                        courseId=courseId,
                        userId=userId,
                        startI=i,
                        document_name=fileName,
                        summary=summary
                    ))
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                logging.info(f"Future {i} is done")
                result = future.result()
                nodes_data.extend(result if result is not None else [])
                SupabaseService.update_note(noteId, 'graphStatus', str(uuid4()))
    except Exception as e:
        logging.exception(f"Error in processing chunks: {e}")
        raise e
    
    SupaGraphService.merge_similar_nodes(courseId)
    logging.info(f"Setting mergeStatus to complete for course {courseId}")

    SupaGraphService.update_embeddings(courseId)
    SupabaseService.update_note(noteId=noteId, key='updatedAt', value=datetime.now())
    logging.info(f"Setting comStatus to complete for course {courseId}")

    SupabaseService.update_note(noteId=noteId, key='graphStatus', value='complete')
    
    logging.info('Updated the nodeCount and relCount properties in Document node')
    logging.info(f'File: {fileName} extraction has been completed')

def process_chunks(
    chunk, 
    noteId,
    courseId,
    userId,
    startI,
    document_name,
    summary
):
    try:
      logging.info(f"Starting process_chunks for chunk {startI}")

      chunk_id = SupaGraphService.insert_chunk(
        noteId=noteId,
        courseId=courseId,
        chunk=chunk,
      )

      logging.info("Get graph document list from models")


      graph_document = get_graph_from_OpenAI(
        chunk=chunk,
        summary=summary,
      )

      graph_doc = clean_nodes(doc=graph_document, courseId=courseId, noteId=noteId, userId=userId)

      nodes_data = SupaGraphService.insert_topics(
        graph_document=graph_doc,
        noteId=noteId
      )

      SupaGraphService.connect_topics(
        nodes=nodes_data,
        chunk_id=chunk_id,
        noteId=noteId,
      )

      return nodes_data
    except Exception as e:
      logging.exception(f"Error in process_chunks: {e}")