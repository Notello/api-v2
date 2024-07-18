from itertools import combinations
import logging
from typing import List, Tuple
import re
import os
import uuid

from flask import current_app
from ..document_sources.youtube import create_youtube_url
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.docstore.document import Document
from langchain_community.graphs import Neo4jGraph
from langchain_community.graphs.graph_document import GraphDocument
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from typing import List, Union
from langchain_groq import ChatGroq

from flask_app.constants import MIXTRAL_MODEL, LLAMA_8_MODEL, GPT_35_TURBO_MODEL, GPT_4O_MODEL

from dotenv import load_dotenv
load_dotenv()


def check_url_source(yt_url:str=None):
    languages=[]
    try:
      logging.info(f"incoming URL: {yt_url}")
      if re.match('(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?',yt_url.strip()):
        youtube_url = create_youtube_url(yt_url.strip())
        logging.info(youtube_url)
        return youtube_url,languages
      else:
        raise Exception('Incoming URL is not youtube URL')
          
    except Exception as e:
      logging.error(f"Error in recognize URL: {e}")
      raise Exception(e)

def get_combined_chunks(chunkId_chunkDoc_list):
    combined_chunk_document_list=[]
    combined_chunks_page_content = ["".join(document['chunk_doc'].page_content for document in chunkId_chunkDoc_list[i:i+1]) for i in range(0, len(chunkId_chunkDoc_list))]
    combined_chunks_ids = [[document['chunk_id'] for document in chunkId_chunkDoc_list[i:i+1]] for i in range(0, len(chunkId_chunkDoc_list))]
    
    for i in range(len(combined_chunks_page_content)):
         combined_chunk_document_list.append(Document(page_content=combined_chunks_page_content[i], metadata={"combined_chunk_ids":combined_chunks_ids[i]}))
    return combined_chunk_document_list


def get_chunk_and_graphDocument(graph_document_list, chunkId_chunkDoc_list):
  logging.info("creating list of chunks and graph documents in get_chunk_and_graphDocument func")
  lst_chunk_chunkId_document=[]

  for graph_document in graph_document_list:            
          for chunk_id in graph_document.source.metadata['combined_chunk_ids']:

            lst_chunk_chunkId_document.append({
              'graph_doc': graph_document,
              'chunk_id': chunk_id
            })
                  
  return lst_chunk_chunkId_document  
                 
def create_graph_database_connection(uri, userName, password, database):
  graph = Neo4jGraph(url=uri, database=database, username=userName, password=password, refresh_schema=False, sanitize=True)
  return graph


def load_embedding_model():
  embeddings = OpenAIEmbeddings()
  dimension = 1536
  logging.info(f"Embedding: Using OpenAI Embeddings , Dimension:{dimension}")
  return embeddings, dimension

def update_graph_documents(
    graph_document_list: List[GraphDocument], 
    noteId: str = None, 
    courseId: str = None, 
    userId: str = None
):
    graphDb_data_Access = graphDBdataAccess(get_graph())

    nodes_data = []
    relationships_data = []

    for graph_document in graph_document_list:
        for node in graph_document.nodes:
            node_data = {
                "id": node.id,
                "uuid": str(uuid.uuid4()),
                "type": node.type,
                "noteId": noteId,
                "courseId": courseId,
                "userId": userId
            }
            if hasattr(node, 'properties') and isinstance(node.properties, dict):
                for key, value in node.properties.items():
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        node_data[key] = value
                    else:
                        node_data[key] = str(value)
            nodes_data.append(node_data)

        for relationship in graph_document.relationships:
            relationships_data.append({
                "source": relationship.source.id,
                "target": relationship.target.id,
                "type": relationship.type
            })

    node_query = """
    UNWIND $nodes AS node
    MERGE (n:Concept {id: node.id})
    ON CREATE SET 
        n.id = node.id,
        n.type = node.type,
        n.noteId = CASE WHEN node.noteId IS NOT NULL THEN [node.noteId] ELSE [] END,
        n.courseId = CASE WHEN node.courseId IS NOT NULL THEN [node.courseId] ELSE [] END,
        n.userId = CASE WHEN node.userId IS NOT NULL THEN [node.userId] ELSE [] END,
        n.uuid = CASE WHEN node.uuid IS NOT NULL THEN [node.uuid] ELSE [] END
    ON MATCH SET
        n.type = node.type,
        n.noteId = CASE 
            WHEN node.noteId IS NOT NULL AND NOT node.noteId IN n.noteId 
            THEN n.noteId + [node.noteId] 
            ELSE n.noteId 
        END,
        n.courseId = CASE 
            WHEN node.courseId IS NOT NULL AND NOT node.courseId IN n.courseId 
            THEN n.courseId + [node.courseId] 
            ELSE n.courseId 
        END,
        n.userId = CASE 
            WHEN node.userId IS NOT NULL AND NOT node.userId IN n.userId 
            THEN n.userId + [node.userId] 
            ELSE n.userId 
        END,
        n.uuid = CASE 
            WHEN node.uuid IS NOT NULL AND NOT node.uuid IN n.uuid 
            THEN n.uuid + [node.uuid] 
            ELSE n.uuid 
        END
    """

    relationship_query = """
    UNWIND $relationships AS rel
    MATCH (source:Concept {id: rel.source})
    MATCH (target:Concept {id: rel.target})
    MERGE (source)-[r:RELATED {type: rel.type}]->(target)
    """

    graphDb_data_Access.execute_query(node_query, {"nodes": nodes_data})
    graphDb_data_Access.execute_query(relationship_query, {"relationships": relationships_data})
   
def close_db_connection(graph, api_name):
  if not graph._driver._closed:
    logging.info(f"closing connection for {api_name} api")
    graph._driver.close()   
      
def get_llm(model_version:str):

  if model_version == GPT_35_TURBO_MODEL or model_version == GPT_4O_MODEL:
    llm = ChatOpenAI(api_key=os.environ.get('OPENAI_KEY'), 
                      model=model_version, 
                      temperature=.1)
    logging.info(f"Model created : Model Version: {model_version}")
    return llm
  elif model_version == MIXTRAL_MODEL or model_version == LLAMA_8_MODEL:
    llm = ChatGroq(api_key=os.environ.get('GROQ_KEY'), 
                    model=model_version, 
                    temperature=.1)
    logging.info(f"Model created : Model Version: {model_version}")
    return llm
  else:
    raise Exception(f"Model Version {model_version} not supported")
  
def compare_similar_words(options, bad_ends=['s', 'ed', 'ing', 'er']):
  words_to_combine = []

  for option in combinations(options, 2):
    word1, word2 = option
    for ending in bad_ends:
      if word1.endswith(ending) and word2 == word1[:-len(ending)]:
        print(f"Yes: {word2} -> {word1}")
        words_to_combine.append((word1, word2))
      elif word2.endswith(ending) and word1 == word2[:-len(ending)]:
        print(f"Yes: {word1} -> {word2}")
        words_to_combine.append((word1, word2))

  return words_to_combine

def get_graph():
  return create_graph_database_connection(
      uri=os.getenv('NEO4J_URI'),
      userName=os.getenv('NEO4J_USERNAME'),
      password=os.getenv('NEO4J_PASSWORD'),
      database=os.getenv('NEO4J_DATABASE')
  )

def embed_name(name: str, embeddings: OpenAIEmbeddings) -> Tuple[str, List[float]]:
  return name, embeddings.embed_query(text=name)