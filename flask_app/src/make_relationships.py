import uuid
from langchain.docstore.document import Document
from flask_app.src.shared.common_fn import load_embedding_model
import logging
from typing import List
from flask import current_app

logging.basicConfig(format='%(asctime)s - %(message)s', level='INFO')

def merge_relationship_between_chunk_and_entites(graph_documents_chunk_chunk_Id : list):
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
                    MERGE (c)-[:HAS_ENTITY]->(n)
                """
        current_app.config['NEO4J_GRAPH'].query(unwind_query, params={"batch_data": batch_data})

    
def update_embedding_create_vector_index(chunkId_chunkDoc_list, file_name):
    embeddings, dimension = load_embedding_model()
    logging.info(f'embedding model:{embeddings} and dimesion:{dimension}')
    data_for_query = []
    logging.info(f"update embedding and vector index for chunks")
    for row in chunkId_chunkDoc_list:

        embeddings_arr = embeddings.embed_query(row['chunk_doc'].page_content)

        data_for_query.append({
            "chunkId": row['chunk_id'],
            "embeddings": embeddings_arr
        })

        current_app.config['NEO4J_GRAPH'].query("""CREATE VECTOR INDEX `vector` if not exists for (c:Chunk) on (c.embedding)
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
        MATCH (d:Document {fileName: $fileName})
        MERGE (c:Chunk {id: row.chunkId})
        SET c.embedding = row.embeddings
        MERGE (c)-[:PART_OF]->(d)
    """       
    current_app.config['NEO4J_GRAPH'].query(query_to_create_embedding, params={"fileName":file_name, "data":data_for_query})
    
def create_relation_between_chunks(file_name, chunks: List[Document])->list:
    logging.info("creating FIRST_CHUNK and NEXT_CHUNK relationships between chunks")
    current_chunk_id = ""
    lst_chunks_including_hash = []
    batch_data = []
    relationships = []
    for i, chunk in enumerate(chunks):
        previous_chunk_id = current_chunk_id
        current_chunk_id = str(uuid.uuid4())
        if i == 0:
            firstChunk = True
        else:
            firstChunk = False  
        metadata = {"position": i + 1,"length": len(chunk.page_content)}
        chunk_document = Document(
            page_content=chunk.page_content, metadata=metadata
        )
        
        chunk_data = {
            "id": current_chunk_id,
            "pg_content": chunk_document.page_content,
            "position": i + 1,
            "length": chunk_document.metadata["length"],
            "f_name": file_name,
            "previous_id" : previous_chunk_id,
        }
        
        if 'page_number' in chunk.metadata:
            chunk_data['page_number'] = chunk.metadata['page_number']
            
        batch_data.append(chunk_data)
        
        lst_chunks_including_hash.append({'chunk_id': current_chunk_id, 'chunk_doc': chunk})
        
        # create relationships between chunks
        if firstChunk:
            relationships.append({"type": "FIRST_CHUNK", "chunk_id": current_chunk_id})
        else:
            relationships.append({
                "type": "NEXT_CHUNK",
                "previous_chunk_id": previous_chunk_id,
                "current_chunk_id": current_chunk_id
            })
          
    query_to_create_chunk_and_PART_OF_relation = """
        UNWIND $batch_data AS data
        MERGE (c:Chunk {id: data.id})
        SET c.text = data.pg_content, c.position = data.position, c.length = data.length, c.fileName=data.f_name
        WITH data, c
        WHERE data.page_number IS NOT NULL
        SET c.page_number = data.page_number
        WITH data, c
        WHERE data.page_number IS NOT NULL
        SET c.page_number = data.page_number
        WITH data, c
        MATCH (d:Document {fileName: data.f_name})
        MERGE (c)-[:PART_OF]->(d)
    """
    current_app.config['NEO4J_GRAPH'].query(query_to_create_chunk_and_PART_OF_relation, params={"batch_data": batch_data})
    
    query_to_create_FIRST_relation = """ 
        UNWIND $relationships AS relationship
        MATCH (d:Document {fileName: $f_name})
        MATCH (c:Chunk {id: relationship.chunk_id})
        FOREACH(r IN CASE WHEN relationship.type = 'FIRST_CHUNK' THEN [1] ELSE [] END |
                MERGE (d)-[:FIRST_CHUNK]->(c))
        """
    current_app.config['NEO4J_GRAPH'].query(query_to_create_FIRST_relation, params={"f_name": file_name, "relationships": relationships})   
    
    query_to_create_NEXT_CHUNK_relation = """ 
        UNWIND $relationships AS relationship
        MATCH (c:Chunk {id: relationship.current_chunk_id})
        WITH c, relationship
        MATCH (pc:Chunk {id: relationship.previous_chunk_id})
        FOREACH(r IN CASE WHEN relationship.type = 'NEXT_CHUNK' THEN [1] ELSE [] END |
                MERGE (c)<-[:NEXT_CHUNK]-(pc))
        """
    current_app.config['NEO4J_GRAPH'].query(query_to_create_NEXT_CHUNK_relation, params={"relationships": relationships})   
    
    return lst_chunks_including_hash

