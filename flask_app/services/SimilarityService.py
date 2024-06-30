import logging
from flask_app.src.shared.common_fn import load_embedding_model

from flask import current_app

class SimilarityService:
    def __init__(self, similarity_threshold, word_edit_distance):
        self.similarity_threshold = similarity_threshold
        self.word_edit_distance = word_edit_distance

    def embed_documents(self, documents, noteId):
        combined_content = " ".join(doc.page_content for doc in documents)

        embeddings, dimension = load_embedding_model()
        embeddings_arr = embeddings.embed_query(text=combined_content)

        logging.info(f"Embedding: Using OpenAI Embeddings , Dimension:{dimension}")

        current_app.config['NEO4J_GRAPH'].query("""
            CREATE VECTOR INDEX `doc_embedding` IF NOT EXISTS FOR (d:Document) ON (d.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: $dimensions,
                `vector.similarity_function`: 'cosine'
            }}
        """, {
            "dimensions": dimension
        })

        ## UPDATE TO BE NOTEID NOT FILENAME
        query_to_create_or_update_document = """
        MERGE (d:Document {noteId: $noteId})
        SET d.embedding = $embedding
        RETURN ID(d) as id
        """

        node = current_app.config['NEO4J_GRAPH'].query(
            query_to_create_or_update_document,
            params={"noteId": noteId, "embedding": embeddings_arr}
        )

        return node, embeddings_arr   

    def find_similar_documents(self, courseId, noteId, documents):
        node, embeddings_arr = self.embed_documents(
            documents=documents, 
            noteId=noteId
            )

        query = """
        CALL db.index.vector.queryNodes('doc_embedding', 1, $queryEmbedding)
        YIELD node AS similarDoc, score AS similarity
        WHERE similarity >= $threshold AND similarDoc.noteId <> $noteId and similarDoc.courseId = $courseId
        RETURN similarDoc.noteId AS noteId, similarity
        ORDER BY similarity DESC
        """

        result = current_app.config['NEO4J_GRAPH'].query(
            query,
            params={
                "courseId": courseId,
                "noteId": noteId,
                "queryEmbedding": embeddings_arr,
                "threshold": self.similarity_threshold
            }
        )

        similar_documents = [
            {"noteId": record["noteId"], "similarity": record["similarity"]}
            for record in result
        ]

        print("similar_documents", similar_documents)

        return node, similar_documents
    
    def has_similar_documents(self, courseId, noteId, documents) -> str | None:
        node, docs = self.find_similar_documents(
            courseId=courseId,
            noteId=noteId,
            documents=documents
            )

        if len(docs) > 0:
            self.delete_node(node[0])
            return docs[0]["noteId"]
        else:
            return None

    def same_youtube_node_exists(self, course_id, url) -> str | None:
        query = """
        MATCH (d:Document)
        WHERE d.courseId = $courseId AND d.url = $url
        RETURN d.noteId as noteId
        LIMIT 1
        """

        result = current_app.config['NEO4J_GRAPH'].query(
            query,
            params={
                "courseId": course_id,
                "url": url
            }
        )

        print("result", result)

        if len(result) > 0:
            return result[0]["noteId"]
        else:
            return None
        
    def delete_node(self, node):
        current_app.config['NEO4J_GRAPH'].query("""
            MATCH (d:Document)
            WHERE ID(d) = $nodeId
            DETACH DELETE d
            """,
            params={"nodeId": node["id"]}
        )