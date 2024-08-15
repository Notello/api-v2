import logging
from typing import Optional
from langchain_core.pydantic_v1 import BaseModel, Field

from flask_app.src.shared.common_fn import get_llm, load_embedding_model
from flask_app.constants import COURSEID, GPT_4O_MINI, NOTEID
from flask_app.services.SupabaseService import SupabaseService
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from langchain.prompts import ChatPromptTemplate

class IsRelated(BaseModel):
    reasoning: Optional[str] = Field(
        description="A reason for the decision, only required if isRelated is false."
    )
    isRelated: bool = Field(
        description="A true/false value indicating if the document summary is in the same subject as the course description."
    )

class SimilarityService:
    def __init__(self, similarity_threshold = 0.98, word_edit_distance = 5):
        self.similarity_threshold = similarity_threshold
        self.word_edit_distance = word_edit_distance

    def embed_documents(self, documents, noteId):
        combined_content = " ".join(doc.page_content for doc in documents)

        embeddings, dimension = load_embedding_model()
        embeddings_arr = embeddings.embed_query(text=combined_content)

        logging.info(f"Embedding: Using OpenAI Embeddings , Dimension:{dimension}")

        graphDBdataAccess().execute_query("""
            CREATE VECTOR INDEX `doc_embedding` IF NOT EXISTS FOR (d:Document) ON (d.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: $dimensions,
                `vector.similarity_function`: 'cosine'
            }}
        """, {
            "dimensions": dimension
        })

        query_to_create_or_update_document = """
        MERGE (d:Document {noteId: $noteId})
        SET d.embedding = $embedding
        RETURN ID(d) as id
        """

        node = graphDBdataAccess().execute_query(
            query_to_create_or_update_document,
            params={NOTEID: noteId, "embedding": embeddings_arr}
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

        result = graphDBdataAccess().execute_query(
            query,
            params={
                COURSEID: courseId,
                NOTEID: noteId,
                "queryEmbedding": embeddings_arr,
                "threshold": self.similarity_threshold
            }
        )

        similar_documents = [
            {NOTEID: record[NOTEID], "similarity": record["similarity"]}
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

        if not SupabaseService.isCollegePrivate(courseId=courseId) and len(docs) > 0:
            self.delete_node(node[0])
            return docs[0][NOTEID]
        else:
            return None

    @staticmethod
    def same_youtube_node_exists(courseId, url) -> str | None:
        query = """
        MATCH (d:Document)
        WHERE d.courseId = $courseId AND d.url = $url
        RETURN d.noteId as noteId
        LIMIT 1
        """

        result = graphDBdataAccess().execute_query(
            query,
            params={
                COURSEID: courseId,
                "url": url
            }
        )

        print("result", result)

        if not SupabaseService.isCollegePrivate(courseId=courseId) and len(result) > 0:
            return result[0][NOTEID]
        else:
            return None
        
    @staticmethod
    def check_youtube_similarity(
        courseId: str,
        noteId: str,
        sourceUrl: str
    ):
        try:
            similar = SimilarityService.same_youtube_node_exists(courseId=courseId, url=sourceUrl)
        except Exception as e:
            logging.exception(f'Exception in same_youtube_node_exists: {e}')
            SupabaseService.update_note(noteId=noteId, key='contentStatus', value='error')
            raise e

        if similar:
            logging.info(f"File: {sourceUrl} is similar to {similar}")
            SupabaseService.update_note(
                noteId=noteId,
                key='matchingNoteId',
                value=similar
            )
            SupabaseService.update_note(
                noteId=noteId, 
                key='graphStatus', 
                value='complete'
                )
            SupabaseService.update_note(
                noteId=noteId, 
                key='contentStatus',
                value='complete'
                )
            
        return similar
        
    def delete_node(self, node):
        graphDBdataAccess().execute_query("""
            MATCH (d:Document)
            WHERE ID(d) = $nodeId
            DETACH DELETE d
            """,
            params={"nodeId": node["id"]}
        )

    @staticmethod
    def same_subject(courseId, documentSummary):
        course = SupabaseService.get_course_description(courseId)
        
        if course is None:
            return None
        
        llm = get_llm(GPT_4O_MINI).with_structured_output(IsRelated)
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are a content classifier with a broad understanding of academic subjects.
            Your task is to determine if the provided document summary is related to the given course information.
            Consider a wide range of potential connections between the document and the course.
            Even if the relationship is not immediately obvious, look for any reasonable links or relevance.
            Consider interdisciplinary connections and how the document might indirectly relate to the course.
            If there's any doubt or if you can find even a tenuous connection, lean towards classifying it as related.
            Only classify as unrelated if there's a clear and significant mismatch between the document and the course.
            If there is not enough information to make a confident decision, classify it as related.
            If you determine it's unrelated, provide a brief explanation for your decision.
            """),
            ("user", f"""
            Please classify the following document summary as related or not related to the course description: 
            Course Name: {course.get('name')}
            Course Number: {course.get('courseNumber')}
            Course Description: {course.get('description')}

            Document Summary:
            {documentSummary}
            """),
        ])

        promptable_llm = prompt | llm

        result: IsRelated = promptable_llm.invoke({})

        logging.info(result.dict())

        if not result.isRelated:
            return {
                "isRelated": False,
                "reasoning": result.reasoning
            }
        else:
            return {
                "isRelated": True
            }
    
    @staticmethod
    def is_related(courseId, documentSummary):
        isPrivate = SupabaseService.isCollegePrivate(courseId=courseId)

        if isPrivate:
            return True
        
        return SimilarityService.same_subject(courseId=courseId, documentSummary=documentSummary)