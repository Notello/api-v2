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
    start_time = datetime.now()
        
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

    end_time = datetime.now()
    processed_time = end_time - start_time
    
    # NodeUpdateService.update_communities_for_param(id_type=NOTEID, target_id=noteId, note_id=noteId)

    SupabaseService.update_note(noteId=noteId, key='graphStatus', value='complete')

    # # Course-level operations now use the updated queuing system
    # NodeUpdateService.merge_similar_nodes(id_type=COURSEID, target_id=courseId, note_id=noteId)
    # graphAccess.update_source_node(sourceNode(noteId = noteId, mergeStatus = "complete"))
    # SupabaseService.update_note(noteId=noteId, key='updatedAt', value=datetime.now())
    # logging.info(f"Setting mergeStatus to complete for course {courseId}")

    # NodeUpdateService.update_embeddings(id_type=COURSEID, target_id=courseId, note_id=noteId, nodes_data=nodes_data)
    # graphAccess.update_source_node(sourceNode(noteId = noteId, embedStatus = "complete"))

    # NodeUpdateService.update_communities_for_param(id_type=COURSEID, target_id=courseId, note_id=noteId)
    # SupabaseService.update_note(noteId=noteId, key='updatedAt', value=datetime.now())
    # graphAccess.update_source_node(sourceNode(noteId = noteId, comStatus = "complete"))
    # logging.info(f"Setting comStatus to complete for course {courseId}")
    
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
      )

      SupaGraphService.insert_chunk_topics(
        nodes=nodes_data,
        chunk_id=chunk_id
      )

      return nodes_data
    except Exception as e:
      logging.exception(f"Error in process_chunks: {e}")