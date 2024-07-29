import logging
from datetime import datetime
import logging

from flask_app.src.entities.source_node import sourceNode
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.make_relationships import create_relation_between_chunks, merge_relationship_between_chunk_and_entities, update_embedding_create_vector_index
from flask_app.src.openAI_llm import get_graph_from_OpenAI
from flask_app.src.shared.common_fn import get_chunk_and_graphDocument, update_graph_documents
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.NodeUpdateService import NodeUpdateService
from flask_app.constants import COURSEID, NOTEID
from flask_app.constants import GPT_4O_MINI

def processing_source(
      graphDb_data_Access: graphDBdataAccess, 
      fileName: str, 
      chunks, 
      userId,
      courseId,
      noteId
      ):
  start_time = datetime.now()
        
  logging.info("Break down file into chunks")

  obj_source_node = sourceNode(
    status = "Processing",
    fileName = fileName,
    noteId = noteId,
    total_chunks = len(chunks),
    model = GPT_4O_MINI,
  )
  graphDb_data_Access.update_source_node(obj_source_node)

  SupabaseService.update_note(noteId, 'graphStatus', '1')
  
  logging.info('Update the status as Processing')

  process_chunks(
    chunks=chunks, 
    noteId=noteId,
    courseId=courseId,
    userId=userId,
    startI=0,
    document_name=fileName
  )

  SupabaseService.update_note(noteId, 'graphStatus', '1')

  end_time = datetime.now()
  processed_time = end_time - start_time
  
  obj_source_node = sourceNode(
    fileName = fileName,
    updated_at = end_time,
    noteId = noteId,
    processing_time = processed_time,
  )
  graphDb_data_Access.update_source_node(obj_source_node)

  NodeUpdateService.update_note_embeddings(noteId=noteId)

  NodeUpdateService.merge_similar_nodes()

  NodeUpdateService.update_communities_for_param(id_type=NOTEID, target_id=noteId)
  NodeUpdateService.update_page_rank(param=NOTEID, id=noteId)

  SupabaseService.update_note(noteId=noteId, key='graphStatus', value='complete')

  NodeUpdateService.update_communities_for_param(id_type=COURSEID, target_id=courseId)
  NodeUpdateService.update_page_rank(param=COURSEID, id=courseId)

  
  logging.info('Updated the nodeCount and relCount properties in Document node')
  logging.info(f'file:{fileName} extraction has been completed')

def process_chunks(
    chunks, 
    noteId,
    courseId,
    userId,
    startI,
    document_name
):
  
  logging.info(f"Starting process_chunks for {len(chunks)} chunks")

  # Creates the first, NEXT_CHUNK relationship between chunks
  chunkId_chunkDoc_list = create_relation_between_chunks(
     noteId=noteId,
     courseId=courseId,
     userId=userId,
     chunks=chunks,
     startI=startI,
     document_name=document_name,
  )

  logging.info(f"Created chunks for {len(chunkId_chunkDoc_list)} chunks between in create_relation_between_chunks")

  # Create vector index and update chunk node with embedding
  update_embedding_create_vector_index(
    chunkId_chunkDoc_list=chunkId_chunkDoc_list, 
    noteId=noteId
  )

  logging.info("Get graph document list from models")

  # Generates graph documents from chunks
  graph_documents = get_graph_from_OpenAI(
    chunkId_chunkDoc_list,
  )

  # Saves graph documents in Neo4j
  update_graph_documents(
    graph_document_list=graph_documents,
    noteId=noteId,
    courseId=courseId,
    userId=userId
  )

  chunks_and_graphDocuments_list = get_chunk_and_graphDocument(
    graph_document_list=graph_documents, 
    chunkId_chunkDoc_list=chunkId_chunkDoc_list
  )

  merge_relationship_between_chunk_and_entities(
    graph_documents_chunk_chunk_Id=chunks_and_graphDocuments_list
  )

  return startI