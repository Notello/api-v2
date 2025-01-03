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

from flask import current_app

def processing_source(
      graphDb_data_Access: graphDBdataAccess, 
      fileName: str, 
      pages, 
      allowedNodes, 
      allowedRelationship,
      userId,
      courseId,
      noteId
      ):
  """
   Extracts a Neo4jGraph from a PDF file based on the model.
   
   Args:
   	 uri: URI of the graph to extract
     db_name : db_name is database name to connect graph db
   	 userName: Username to use for graph creation ( if None will use username from config file )
   	 password: Password to use for graph creation ( if None will use password from config file )
   	 file: File object containing the PDF file to be used
   	 model: Type of model to use ('Diffbot'or'OpenAI GPT')
   
   Returns: 
   	 Json response to API with fileName, nodeCount, relationshipCount, processingTime, 
     status and model as attributes.
  """
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
  
  logging.info('Update the status as Processing')
  updateGraphChunkProcessed = int(current_app.config['UPDATE_GRAPH_CHUNKS_PROCESSED'])
  for i in range(0, len(chunks), updateGraphChunkProcessed):
    select_chunks_upto = min(i + updateGraphChunkProcessed, len(chunks))

    logging.info(f'Selected Chunks upto: {select_chunks_upto}')

    selected_chunks = chunks[i : select_chunks_upto]

    process_chunks(
      chunks=selected_chunks, 
      allowedNodes=allowedNodes,
      allowedRelationship=allowedRelationship, 
      noteId=noteId,
      courseId=courseId,
      userId=userId,
      startI=i
    )

    SupabaseService.update_note(noteId, 'graphStatus', str(select_chunks_upto))

  end_time = datetime.now()
  processed_time = end_time - start_time
  
  obj_source_node = sourceNode(
    fileName = fileName,
    updated_at = end_time,
    noteId = noteId,
    processing_time = processed_time,
  )
  graphDb_data_Access.update_source_node(obj_source_node)
  
  logging.info('Updated the nodeCount and relCount properties in Document node')
  logging.info(f'file:{fileName} extraction has been completed')

def process_chunks(
    chunks, 
    allowedNodes,
    allowedRelationship, 
    noteId,
    courseId,
    userId,
    startI
):

  # Creates the first, NEXT_CHUNK relationship between chunks
  chunkId_chunkDoc_list = create_relation_between_chunks(
     noteId=noteId,
     courseId=courseId,
     userId=userId,
     chunks=chunks,
     startI=startI
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
    allowedNodes,
    allowedRelationship
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