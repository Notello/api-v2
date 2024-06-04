import os
import sys
from pytube import YouTube
from datetime import datetime
import logging
import re
from flask_app.src.create_chunks import CreateChunksofDocument
from flask_app.src.document_sources.youtube import get_documents_from_youtube, get_youtube_transcript
from flask_app.src.entities.source_node import sourceNode
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.make_relationships import create_relation_between_chunks, merge_relationship_between_chunk_and_entites, update_embedding_create_vector_index
from flask_app.src.openAI_llm import get_graph_from_OpenAI
from flask_app.src.shared.common_fn import check_url_source, get_chunk_and_graphDocument, save_graphDocuments_in_neo4j
from langchain_core.documents import Document

from flask import current_app

def create_source_node_graph_url_youtube(source_url, noteId, courseId, userId):
    
    youtube_url, language = check_url_source(yt_url=source_url)
    success_count=0
    failed_count=0
    lst_file_name = []
    obj_source_node = sourceNode()
    obj_source_node.file_type = 'text'
    obj_source_node.file_source = 'youtube'
    obj_source_node.model = current_app.config['MODEL']
    obj_source_node.courseId = courseId
    obj_source_node.userId = userId
    obj_source_node.url = youtube_url
    obj_source_node.created_at = datetime.now()
    obj_source_node.noteId = noteId
    match = re.search(r'(?:v=)([0-9A-Za-z_-]{11})\s*',obj_source_node.url)
    logging.info(f"match value{match}")

    transcript= get_youtube_transcript(match.group(1))

    if transcript==None or len(transcript)==0:
      message = f"Youtube transcript is not available for : {obj_source_node.fileName}"
      raise Exception(message)
    else:  
      obj_source_node.file_size = sys.getsizeof(transcript)
    
    graphDb_data_Access: graphDBdataAccess = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])

    print("BEFOREBSICAS BOCA C ALJCA")

    file_name, pages = get_documents_from_youtube(obj_source_node.url)

    obj_source_node.fileName = file_name

    graphDb_data_Access.create_source_node(obj_source_node)

    lst_file_name.append({'fileName':obj_source_node.fileName,'fileSize':obj_source_node.file_size,'url':obj_source_node.url,'status':'Success'})
    success_count+=1

    processing_source(
       graphDb_data_Access=graphDb_data_Access,
       file_name=file_name,
       pages=pages,
       allowedNodes=[], 
       allowedRelationship=[])

    return lst_file_name,success_count,failed_count

def processing_source(graphDb_data_Access: graphDBdataAccess, file_name, pages, allowedNodes, allowedRelationship):
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

  result = graphDb_data_Access.get_current_status_document_node(file_name)

  print("pages", pages)
  
  if result[0]['Status'] != 'Processing':
    
    bad_chars = ['"', "\n", "'"]
    for i in range(0,len(pages)):
      text = pages[i].page_content
      for j in bad_chars:
        if j == '\n':
          text = text.replace(j, ' ')
        else:
          text = text.replace(j, '')
      pages[i]=Document(page_content=str(text), metadata=pages[i].metadata)
      
    logging.info("Break down file into chunks")
    
    create_chunks_obj = CreateChunksofDocument(pages, file_name)
    chunks = create_chunks_obj.split_file_into_chunks()

    obj_source_node = sourceNode()
    status = "Processing"
    obj_source_node.fileName = file_name
    obj_source_node.status = status
    obj_source_node.total_pages = len(pages)
    obj_source_node.total_chunks = len(chunks)
    obj_source_node.model = current_app.config['MODEL']
    logging.info(file_name)
    logging.info(obj_source_node)
    graphDb_data_Access.update_source_node(obj_source_node)
    
    logging.info('Update the status as Processing')
    update_graph_chunk_processed = int(current_app.config['UPDATE_GRAPH_CHUNKS_PROCESSED'])
    # selected_chunks = []
    is_cancelled_status = False
    job_status = "Completed"
    node_count = 0
    rel_count = 0
    for i in range(0, len(chunks), update_graph_chunk_processed):
      select_chunks_upto = i+update_graph_chunk_processed
      logging.info(f'Selected Chunks upto: {select_chunks_upto}')
      if len(chunks) <= select_chunks_upto:
         select_chunks_upto = len(chunks)
      selected_chunks = chunks[i:select_chunks_upto]
      result = graphDb_data_Access.get_current_status_document_node(file_name)
      is_cancelled_status = result[0]['is_cancelled']
      logging.info(f"Value of is_cancelled : {result[0]['is_cancelled']}")
      if is_cancelled_status == True:
         job_status = "Cancelled"
         logging.info('Exit from running loop of processing file')
         exit
      else:
        node_count,rel_count = processing_chunks(selected_chunks, 
                                                 file_name, 
                                                 allowedNodes,
                                                 allowedRelationship, 
                                                 node_count, 
                                                 rel_count)
        end_time = datetime.now()
        processed_time = end_time - start_time
        
        obj_source_node = sourceNode()
        obj_source_node.fileName = file_name
        obj_source_node.updated_at = end_time
        obj_source_node.processing_time = processed_time
        obj_source_node.node_count = node_count
        obj_source_node.processed_chunk = select_chunks_upto
        obj_source_node.relationship_count = rel_count
        graphDb_data_Access.update_source_node(obj_source_node)
    
    result = graphDb_data_Access.get_current_status_document_node(file_name)
    is_cancelled_status = result[0]['is_cancelled']
    if is_cancelled_status == 'True':
       logging.info(f'Is_cancelled True at the end extraction')
       job_status = 'Cancelled'
    logging.info(f'Job Status at the end : {job_status}')
    end_time = datetime.now()
    processed_time = end_time - start_time
    obj_source_node = sourceNode()
    obj_source_node.fileName = file_name
    obj_source_node.status = job_status
    obj_source_node.processing_time = processed_time

    graphDb_data_Access.update_source_node(obj_source_node)
    logging.info('Updated the nodeCount and relCount properties in Docuemnt node')
    logging.info(f'file:{file_name} extraction has been completed')
      
    return {
        "fileName": file_name,
        "nodeCount": node_count,
        "relationshipCount": rel_count,
        "processingTime": round(processed_time.total_seconds(),2),
        "status" : job_status,
        "model" : current_app.config['MODEL'],
        "success_count" : 1
    }
  else:
     logging.info('File does not process because it\'s already in Processing status')

def processing_chunks(chunks, file_name, allowedNodes,allowedRelationship, node_count, rel_count):
  chunkId_chunkDoc_list = create_relation_between_chunks(file_name,chunks)
  #create vector index and update chunk node with embedding
  update_embedding_create_vector_index(chunkId_chunkDoc_list, file_name)
  logging.info("Get graph document list from models")
  graph_documents = get_graph_from_OpenAI(chunkId_chunkDoc_list, allowedNodes, allowedRelationship)
  save_graphDocuments_in_neo4j(current_app.config['NEO4J_GRAPH'], graph_documents)
  chunks_and_graphDocuments_list = get_chunk_and_graphDocument(graph_documents, chunkId_chunkDoc_list)
  merge_relationship_between_chunk_and_entites(chunks_and_graphDocuments_list)
  
  distinct_nodes = set()
  relations = []
  for graph_document in graph_documents:
    #get distinct nodes
    for node in graph_document.nodes:
          node_id = node.id
          node_type= node.type
          if (node_id, node_type) not in distinct_nodes:
            distinct_nodes.add((node_id, node_type))
  #get all relations
  for relation in graph_document.relationships:
        relations.append(relation.type)

  node_count += len(distinct_nodes)
  rel_count += len(relations)
  print(f'node count internal func:{node_count}')
  print(f'relation count internal func:{rel_count}')
  return node_count,rel_count