import uuid
from langchain.docstore.document import Document
from flask_app.src.shared.common_fn import clean_chunk_text, load_embedding_model, embed_chunk
import logging
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.constants import COURSEID, NOTEID, USERID

logging.basicConfig(format='%(asctime)s - %(message)s', level='INFO')

@staticmethod
def merge_relationship_between_chunk_and_entities(nodes_data, chunk_with_id, graphAccess: graphDBdataAccess):
    unwind_query = f"""
        UNWIND $nodes_data AS node
        MATCH (c:Chunk {{id: '{chunk_with_id.get('id')}'}})
        MATCH (n:Concept {{uuid: node['uuid']}})
        MERGE (c)-[r:REFERENCES {{type: 'HAS_ENTITY'}}]->(n)
    """
    graphAccess.execute_query(unwind_query, {"nodes_data": nodes_data})

def update_chunk_embedding(chunk, graphAccess: graphDBdataAccess):
    embeddings, dimension = load_embedding_model()
    logging.info(f"update embedding and vector index for chunks")

    emedding = embeddings.embed_query(text=chunk.get('pg_content'))
    
    query_to_create_embedding = f"""
        MATCH (c:Chunk {{id: '{chunk.get('id')}'}})
        SET c.embedding = {emedding}
    """       
    graphAccess.execute_query(query_to_create_embedding)


def create_relation_between_chunks(
        noteId, 
        courseId, 
        userId, 
        chunk: Document,
        startI,
        document_name,
        graphAccess: graphDBdataAccess
        ) -> list:
    try:
        logging.info("creating FIRST_CHUNK relationships between chunks")
        current_chunk_id = str(uuid.uuid4())
        
        chunk_data = {
            "id": current_chunk_id,
            "pg_content": clean_chunk_text(chunk.page_content),
            "position": startI + 1,
            "length": len(chunk.page_content),
            NOTEID: noteId,
            COURSEID: courseId,
            USERID: userId,
            "document_name": document_name,
            "offset": chunk.metadata.get("start"),
        }
                
        chunk_to_doc = f"""
            WITH $chunk_data AS data
            MERGE (c:Chunk {{id: data.id}})
            SET 
            c.text = data.pg_content, 
            c.position = data.position, 
            c.length = data.length, 
            c.noteId = data.noteId,
            c.courseId = data.courseId,
            c.userId = data.userId,
            c.document_name = data.document_name,
            c.offset = data.offset

            WITH c

            MATCH (d:Document {{noteId: '{noteId}'}})
            MERGE (c)-[r:HAS_DOCUMENT {{type: 'PART_OF'}}]->(d)

            WITH c
            MATCH (prev:Chunk {{noteId: '{noteId}', position: c.position - 1}})
            MERGE (prev)-[:NEXT_CHUNK]->(c)
        """

        graphAccess.execute_query(chunk_to_doc, {"chunk_data": chunk_data})
        
        return chunk_data
    except Exception as e:
        logging.error(f"Error in create_relation_between_chunks: {e}")
        raise e