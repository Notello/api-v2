from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import logging
from datetime import datetime
import logging
from uuid import uuid4

from flask_app.src.entities.source_node import sourceNode
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.make_relationships import create_relation_between_chunks, merge_relationship_between_chunk_and_entities, update_chunk_embedding
from flask_app.src.shared.common_fn import clean_nodes
from flask_app.src.openAI_llm import get_graph_from_OpenAI
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.NodeUpdateService import NodeUpdateService
from flask_app.constants import COURSEID, NOTEID
from flask_app.constants import GPT_4O_MINI

def processing_source(
      graphAccess: graphDBdataAccess, 
      fileName: str, 
      chunks, 
      userId,
      courseId,
      noteId,
      summary
      ):
    start_time = datetime.now()
        
    logging.info("Break down file into chunks")

    obj_source_node = sourceNode(
        status = "processing",
        comStatus = "incomplete",
        pagerankStatus = "incomplete",
        mergeStatus = "incomplete",
        fileName = fileName,
        noteId = noteId,
        total_chunks = len(chunks),
        model = GPT_4O_MINI,
    )
    graphAccess.update_source_node(obj_source_node)

    SupabaseService.update_note(noteId, 'graphStatus', '1')
    
    logging.info('Update the status as Processing')

    futures = []
    nodes_data = []

    logging.info(f"Total chunks: {len(chunks)}")

    try:
        with ThreadPoolExecutor(max_workers=200) as executor:
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
                        graphAccess=graphAccess,
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
    
    NodeUpdateService.update_embeddings(noteId=noteId, nodes_data=nodes_data)

    # NodeUpdateService.merge_similar_nodes(id_type=NOTEID, target_id=noteId, note_id=noteId)

    NodeUpdateService.update_communities_for_param(id_type=NOTEID, target_id=noteId, note_id=noteId)
    NodeUpdateService.update_page_rank(id_type=NOTEID, target_id=noteId, note_id=noteId)

    SupabaseService.update_note(noteId=noteId, key='graphStatus', value='complete')

    obj_source_node = sourceNode(
        fileName = fileName,
        status = "complete",
        updated_at = end_time,
        noteId = noteId,
        processing_time = processed_time,
    )

    graphAccess.update_source_node(obj_source_node)

    # Course-level operations now use the updated queuing system
    NodeUpdateService.merge_similar_nodes(id_type=COURSEID, target_id=courseId, note_id=noteId)
    graphAccess.update_source_node(sourceNode(noteId = noteId, mergeStatus = "complete"))
    logging.info(f"Setting mergeStatus to complete for course {courseId}")

    NodeUpdateService.update_communities_for_param(id_type=COURSEID, target_id=courseId, note_id=noteId)
    graphAccess.update_source_node(sourceNode(noteId = noteId, comStatus = "complete"))
    logging.info(f"Setting comStatus to complete for course {courseId}")

    NodeUpdateService.update_page_rank(id_type=COURSEID, target_id=courseId, note_id=noteId)
    graphAccess.update_source_node(sourceNode(noteId = noteId, pagerankStatus = "complete"))
    logging.info(f"Setting pagerankStatus to complete for course {courseId}")
    
    logging.info('Updated the nodeCount and relCount properties in Document node')
    logging.info(f'File: {fileName} extraction has been completed')

def process_chunks(
    chunk, 
    noteId,
    courseId,
    userId,
    startI,
    document_name,
    graphAccess,
    summary
):
    try:
      logging.info(f"Starting process_chunks for chunk {startI}")

      chunk_with_id = create_relation_between_chunks(
        noteId=noteId,
        courseId=courseId,
        userId=userId,
        chunk=chunk,
        startI=startI,
        document_name=document_name,
        graphAccess=graphAccess
      )

      # Create vector index and update chunk node with embedding
      update_chunk_embedding(
        chunk=chunk_with_id,
        graphAccess=graphAccess
      )

      logging.info("Get graph document list from models")


      # Generates graph documents from chunks
      graph_document = get_graph_from_OpenAI(
        chunk_with_id=chunk_with_id,
        summary=summary,
        courseId=courseId,
        userId=userId,
        noteId=noteId
      )

      graph_doc = clean_nodes(doc=graph_document, courseId=courseId, noteId=noteId, userId=userId)


      # Saves graph documents in Neo4j
      nodes_data = NodeUpdateService.update_graph_documents(
        graph_document=graph_doc,
        graphAccess=graphAccess,
      )

      # logging.info(f"Graph documents: {nodes_data}")

      merge_relationship_between_chunk_and_entities(
        chunk_with_id=chunk_with_id,
        nodes_data=nodes_data,
        graphAccess=graphAccess
      )

      return nodes_data
    except Exception as e:
      logging.exception(f"Error in process_chunks: {e}")