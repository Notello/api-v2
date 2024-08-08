import uuid
from langchain.docstore.document import Document
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from flask_app.src.shared.common_fn import get_graph, load_embedding_model, embed_chunk
import logging
from typing import List
from neo4j.exceptions import ClientError, TransientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from flask_app.services.Neo4jTransactionManager import transactional
from flask_app.constants import COURSEID, NOTEID, USERID

logging.basicConfig(format='%(asctime)s - %(message)s', level='INFO')

@staticmethod
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception_type((ClientError, TransientError, AttributeError)),
    reraise=True
)
@transactional
def merge_relationship_between_chunk_and_entities(tx, graph_documents_chunk_chunk_Id : list):
    batch_data = []
    logging.info("Create HAS_ENTITY relationship between chunks and entities")
    for graph_doc_chunk_id in graph_documents_chunk_chunk_Id:
        for node in graph_doc_chunk_id['graph_doc'].nodes:
            query_data={
                'chunk_id': graph_doc_chunk_id['chunk_id'],
                'node_type': node.type,
                'node_id': node.id
            }
            batch_data.append(query_data)

    if batch_data:
        unwind_query = """
                    UNWIND $batch_data AS data
                    MATCH (c:Chunk {id: data.chunk_id})
                    CALL apoc.merge.node([data.node_type], {id: data.node_id}) YIELD node AS n
                    MERGE (c)-[r:REFERENCES {type: 'HAS_ENTITY'}]->(n)
                """
        tx.run(unwind_query, {"batch_data": batch_data})

def update_embedding_create_vector_index(chunkId_chunkDoc_list, noteId):
    embeddings, dimension = load_embedding_model()
    data_for_query = []
    futures = []
    logging.info(f"update embedding and vector index for chunks")

    with ThreadPoolExecutor(max_workers=150) as executor:
        for row in chunkId_chunkDoc_list:
            futures.append(
                executor.submit(
                    embed_chunk,
                    embeddings=embeddings,
                    row=row
                ))

        for future in concurrent.futures.as_completed(futures):
            id, embedding = future.result()

            logging.info(f"Embedded: {id}")

            data_for_query.append({
                "chunkId": id,
                "embeddings": embedding
            })

    get_graph().query("""CREATE VECTOR INDEX `vector` if not exists for (c:Chunk) on (c.embedding)
                    OPTIONS {indexConfig: {
                    `vector.dimensions`: $dimensions,
                    `vector.similarity_function`: 'cosine'
                    }}
                """,
                {
                    "dimensions" : dimension
                }
                )
    
    query_to_create_embedding = """
        UNWIND $data AS row
        MATCH (d:Document {noteId: $noteId})
        MERGE (c:Chunk {id: row.chunkId})
        SET c.embedding = row.embeddings
        MERGE (c)-[r:HAS_DOCUMENT {type: 'PART_OF'}]->(d)
    """       
    get_graph().query(query_to_create_embedding, {NOTEID: noteId, "data": data_for_query})

    logging.info(f"Updated embeddings for {len(data_for_query)} chunks")

def create_relation_between_chunks(
        noteId, 
        courseId, 
        userId, 
        chunk: Document,
        startI,
        document_name
        ) -> list:
    logging.info("creating FIRST_CHUNK relationships between chunks")
    chunk_list = []
    current_chunk_id = str(uuid.uuid4())
    
    chunk_data = {
        "id": current_chunk_id,
        "pg_content": chunk.page_content,
        "position": startI + 1,
        "length": len(chunk.page_content),
        NOTEID: noteId,
        COURSEID: courseId,
        USERID: userId,
        "document_name": document_name,
        "offset": chunk.metadata.get("start"),
    }
    
    chunk_list.append({'chunk_id': current_chunk_id, 'chunk_doc': chunk})
          
    query_to_create_chunk_and_PART_OF_relation = """
        WITH $chunk_data AS data
        MERGE (c:Chunk {id: data.id})
        SET 
        c.text = data.pg_content, 
        c.position = data.position, 
        c.length = data.length, 
        c.noteId = data.noteId,
        c.courseId = data.courseId,
        c.userId = data.userId,
        c.document_name = data.document_name,
        c.offset = data.offset

        WITH data, c
        WHERE data.page_number IS NOT NULL
        SET c.page_number = data.page_number
        WITH data, c
        WHERE data.page_number IS NOT NULL
        SET c.page_number = data.page_number
        WITH data, c
        MATCH (d:Document {noteId: data.noteId})
        MERGE (c)-[r:HAS_DOCUMENT {type: 'PART_OF'}]->(d)
    """
    get_graph().query(query_to_create_chunk_and_PART_OF_relation, {"chunk_data": chunk_data})
    
    return chunk_list

