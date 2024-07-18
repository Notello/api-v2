from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import logging
from datetime import datetime
import logging

from flask_app.src.create_chunks import CreateChunksofDocument
from flask_app.src.entities.source_node import sourceNode
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.make_relationships import create_relation_between_chunks, merge_relationship_between_chunk_and_entities, update_embedding_create_vector_index
from flask_app.src.openAI_llm import get_graph_from_OpenAI
from flask_app.src.shared.common_fn import get_chunk_and_graphDocument, update_graph_documents
from flask_app.services.SupabaseService import SupabaseService
from flask_app.src.process_file import clean_file
from flask_app.services.NodeUpdateService import NodeUpdateService
from flask import current_app

def processing_source(
      graphDb_data_Access: graphDBdataAccess, 
      fileName: str, 
      pages, 
      userId,
      courseId,
      noteId
      ):
  start_time = datetime.now()
    
  clean_file(pages)
    
  logging.info("Break down file into chunks")

  create_chunks_obj = CreateChunksofDocument(pages, fileName)
  chunks = create_chunks_obj.split_file_into_chunks()

  obj_source_node = sourceNode(
    status = "Processing",
    fileName = fileName,
    noteId = noteId,
    total_pages = len(pages),
    total_chunks = len(chunks),
    model = current_app.config['MODEL'],
  )
  graphDb_data_Access.update_source_node(obj_source_node)

  SupabaseService.update_note(noteId, 'graphStatus', '1')

  offsets = {0: 0}

  futures = []
  
  logging.info('Update the status as Processing')
    
  with ThreadPoolExecutor(max_workers=10) as executor:
    for i in range(0, len(chunks)):
      selected_chunks = chunks[i : i + 1]
      offsets[i + 1] = sum([len(chunk.page_content) for chunk in selected_chunks])
      futures.append(
          executor.submit(
              process_chunks,
              chunks=selected_chunks, 
              noteId=noteId,
              courseId=courseId,
              userId=userId,
              startI=i,
              offset=offsets[i],
              document_name=fileName
          ))

    for future in concurrent.futures.as_completed(futures):
      logging.info(f'Processed chunk {i}')

      i = future.result()

      SupabaseService.update_note(noteId, 'graphStatus', str(i))

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

  NodeUpdateService.update_communities_for_param(id_type='noteId', target_id=noteId)
  NodeUpdateService.update_communities_for_param(id_type='courseId', target_id=courseId)

  NodeUpdateService.update_page_rank(param='noteId', id=noteId)
  NodeUpdateService.update_page_rank(param='courseId', id=courseId)
  
  logging.info('Updated the nodeCount and relCount properties in Document node')
  logging.info(f'file:{fileName} extraction has been completed')

def process_chunks(
    chunks, 
    noteId,
    courseId,
    userId,
    startI,
    offset,
    document_name
):

  # Creates the first, NEXT_CHUNK relationship between chunks
  chunkId_chunkDoc_list = create_relation_between_chunks(
     noteId=noteId,
     courseId=courseId,
     userId=userId,
     chunks=chunks,
     startI=startI,
     document_name=document_name,
     offset=offset
  )

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