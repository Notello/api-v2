from itertools import combinations
import logging
from typing import List, Tuple
import re
import os
from uuid import uuid4

from ..document_sources.youtube import create_youtube_url
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.docstore.document import Document
from langchain_community.graphs import Neo4jGraph
from typing import List
from langchain_groq import ChatGroq
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.constants import COURSEID, GROQ_MODELS, NOTEID, OPENAI_MODELS, USERID
from flask_app.src.entities.KnowledgeGraph import KnowledgeGraph

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
                 
def create_graph_database_connection(uri, userName, password, database):
  logging.info(f"Creating graph database connection with uri: {uri}, userName: {userName}, database: {database}")
  graph = Neo4jGraph(url=uri, database=database, username=userName, password=password, refresh_schema=False, sanitize=True)
  return graph


def load_embedding_model(
    retry_max_seconds=1,
    retry_min_seconds=0.1,
    max_retries=1
):
  embeddings = OpenAIEmbeddings(max_retries=max_retries, retry_max_seconds=retry_max_seconds, retry_min_seconds=retry_min_seconds)
  dimension = 1536
  logging.info(f"Embedding: Using OpenAI Embeddings , Dimension:{dimension}")
  return embeddings, dimension
   
def close_db_connection(graph, api_name):
  if not graph._driver._closed:
    logging.info(f"closing connection for {api_name} api")
    graph._driver.close()   
      
def get_llm(model_version:str):

  if model_version in OPENAI_MODELS:
    llm = ChatOpenAI(api_key=os.environ.get('OPENAI_KEY'), 
                      model=model_version, 
                      temperature=.1)
    return llm
  elif model_version in GROQ_MODELS:
    llm = ChatGroq(api_key=os.environ.get('GROQ_KEY'), 
                    model=model_version, 
                    temperature=.1)
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
  logging.info(f"Embedding name: {name}")
  return name, embeddings.embed_query(text=name)

def embed_chunk(row, embeddings: OpenAIEmbeddings) -> Tuple[str, List[float]]:
  return row['chunk_id'], embeddings.embed_query(text=row['chunk_doc'].page_content)

def clean_chunk_text(chunk_text):
    return chunk_text.replace('\n', ' ').replace('.', ' ')


def clean_node_id(node_id):
    return node_id.replace('-', ' ').replace(':', ' ').replace('_', ' ')

def clean_nodes(doc: KnowledgeGraph, courseId: str, noteId: str, userId: str):
  node_uuid_map = {}
  nodes = doc.nodes
  rels = doc.relationships

  output_kg = {"nodes": [], "relationships": []}

  for node in nodes:
    new_node = {}
    new_uuid = str(uuid4())
    new_node['id'] = clean_node_id(node.id)
    new_node['description'] = node.description
    new_node['uuid'] = [new_uuid]
    new_node[COURSEID] = [courseId]
    new_node[USERID] = [userId]
    new_node[NOTEID] = [noteId]
    node_uuid_map[node.id] = new_uuid
    output_kg['nodes'].append(new_node)

  for rel in rels:
    new_rel = {}
    new_rel['type'] = rel.type
    new_rel['source_uuid'] = [node_uuid_map.get(clean_node_id(rel.source))]
    new_rel['target_uuid'] = [node_uuid_map.get(clean_node_id(rel.target))]
    if new_rel['source_uuid'] and new_rel['source_uuid'] != [None] and new_rel['target_uuid'] and new_rel['target_uuid'] != [None]:
      output_kg['relationships'].append(new_rel)

  return output_kg

def init_indexes():
  graphAccess = graphDBdataAccess()
  embeddings, dimension = load_embedding_model()
  graphAccess.execute_query(f"""CREATE VECTOR INDEX `vector` if not exists for (c:Chunk) on (c.embedding)
                OPTIONS {{indexConfig: {{
                `vector.dimensions`: {dimension},
                `vector.similarity_function`: 'cosine'
                }}}}
            """)
  
  logging.info("Created or updated embedding index")
  
  graphAccess.execute_query(f"""
        CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
        FOR (n:Concept)
        ON (n.embedding)
        OPTIONS {{indexConfig: {{
        `vector.dimensions`: {dimension},
        `vector.similarity_function`: 'cosine'
        }}}}
        """)
  
  logging.info("Created or updated concept embedding index")