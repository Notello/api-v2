import logging
from typing import Optional
from langchain_core.pydantic_v1 import BaseModel, Field

from flask_app.src.shared.common_fn import get_llm, load_embedding_model
from flask_app.constants import COURSEID, GPT_4O_MINI, LLAMA_8_MODEL, NOTEID
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
        pass

    def find_similar_documents(self, courseId, noteId, documents):
        pass
    
    def has_similar_documents(self, courseId, noteId, documents) -> str | None:
        pass

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

        if len(result) > 0:
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
            You are a content classifier who will determine if uploaded content is plausibly related to a college course.
            You will be provided with a description of the course and a summary of the content being uploaded.
            It is ok if the subject of the content is not directly related the course, but it should be related at least tennatively.
            If you are uncertain, please classify the content as related.
            If content is about the course itself, or the structure of the course, classify it as related.
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