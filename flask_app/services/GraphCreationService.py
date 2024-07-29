from datetime import datetime
import sys
import logging
from typing import Dict, List
import json
from langchain.docstore.document import Document

from flask_app.services.SupabaseService import SupabaseService
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.entities.source_node import sourceNode
from flask_app.src.main import processing_source
from flask_app.src.document_sources.text_loader import get_text_chunks_langchain
from flask_app.services.TimestampService import TimestampService
from flask_app.services.ChunkService import ChunkService
from flask_app.services.SimilarityService import SimilarityService
from flask_app.models.Quiz import QuizQuestion
from flask_app.services.HelperService import HelperService
from flask_app.src.shared.common_fn import get_graph
from flask_app.constants import COURSEID, NOTEID, USERID, GPT_4O_MINI

class GraphCreationService:
    @staticmethod
    def create_graph_from_timestamps(
        timestamps: List[Dict[str, str]],
        import_type: str,
        document_name: str,
        noteId: str,
        courseId: str,
        userId: str
    ) -> None:
        try:
            chunks = ChunkService.get_timestamp_chunks(transcript=timestamps)

            GraphCreationService.create_graph(
                noteId=noteId,
                courseId=courseId,
                userId=userId,
                fileName=document_name,
                import_type=import_type,
                chunks=chunks
            )
            
        except Exception as e:
            logging.exception(f'Exception in create_source_node_graph_url_youtube: {e}')
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')

    @staticmethod
    def create_graph_from_raw_text(  
        noteId: str,
        courseId: str,
        userId: str,
        rawText: str,
        fileName: str
    ) -> None:
            
        try:
            chunks = ChunkService.get_text_chunks(rawText)

            similarityService = SimilarityService(
                similarity_threshold=0.9, 
                word_edit_distance=5
            )

            similar = similarityService.has_similar_documents(
                courseId=courseId,
                noteId=noteId,
                documents=chunks
            )

            if similar:
                logging.info(f"File: {fileName} is similar to {similar}")
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
                return
    
            GraphCreationService.create_graph(
                noteId=noteId,
                courseId=courseId,
                userId=userId,
                fileName=fileName,
                import_type='text',
                chunks=chunks
            )

            logging.info(f'File {fileName} has been processed successfully')
        except Exception as e:
            logging.exception(f'Exception: {e}')
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')

    @staticmethod
    def create_graph(
        noteId: str,
        courseId: str,
        userId: str,
        fileName: str,
        import_type: str,
        chunks: List[Document],
    ):
        obj_source_node = sourceNode(
            file_source=import_type,
            model=GPT_4O_MINI,
            courseId=courseId,
            userId=userId,
            created_at=datetime.now(),
            noteId=noteId,
        )
        
        graphDb_data_Access: graphDBdataAccess = graphDBdataAccess(get_graph())

        graphDb_data_Access.create_source_node(obj_source_node)

        processing_source(
            graphDb_data_Access=graphDb_data_Access,
            fileName=fileName,
            chunks=chunks,
            userId=userId,
            courseId=courseId,
            noteId=noteId
            )

    @staticmethod
    def insert_quiz_question(questions: List[QuizQuestion]) -> None:
        graphAccess = graphDBdataAccess(get_graph())
        
        query = """
        UNWIND $questions AS q
        CREATE (question:QuizQuestion {
            id: q.questionId,
            userId: q.userId,
            courseId: q.courseId,
            noteId: q.noteId,
            quizId: q.quizId,
            question: q.question,
            answers: q.answers,
            topics: q.topics,
            chunkIds: q.chunkIds,
            difficulty: q.difficulty
        })
        
        WITH question, q
        UNWIND q.topics AS topicId
        MATCH (concept:Concept {id: topicId})
        CREATE (concept)-[:HAS_QUESTION]->(question)
        
        WITH question, q
        UNWIND q.chunkIds AS chunkId
        MATCH (chunk:Chunk {id: chunkId})
        CREATE (chunk)-[:HAS_QUESTION]->(question)
        
        RETURN q
        """

        params = {'questions': [
            {
                'questionId': q['questionId'],
                'quizId': q['quizId'],
                USERID: q[USERID],
                COURSEID: q[COURSEID],
                NOTEID: q[NOTEID] if q[NOTEID] != [None] else "None",
                'question': q['question'],
                'difficulty': q['difficulty'],
                'answers': json.dumps([{  # When getting answers, need to do json.loads()
                    'label': a['label'],
                    'correct': a['correct'],
                    'explanation': a['explanation']
                } for a in q['answers']]),
                'chunkIds': q['chunkIds'],
                'topics': q['topics'],
            } for q in questions
        ]}

        print(params)
        print(query)
        
        graphAccess.execute_query(query, params)

    def insert_summaries(summaries: List[Dict[str, str]]) -> None:
        graphAccess = graphDBdataAccess(get_graph())
        
        query = """
        UNWIND $summaries AS s
        CREATE (summary:Summary {
            userId: s.userId,
            courseId: s.courseId,
            noteId: s.noteId,
            content: s.content,
            concept: s.concept,
            topicId: s.topicId
        })

        WITH summary, s
        MATCH (concept:Concept)
        WHERE s.topicId IN concept.uuid
        CREATE (concept)-[:HAS_SUMMARY]->(summary)
        
        RETURN s
        """

        params = {'summaries': [
            {
                USERID: s[USERID],
                COURSEID: s[COURSEID],
                NOTEID: s[NOTEID],
                'content': s['content'],
                'concept': s['concept'],
                'topicId': s['topicId'],
            } for s in summaries
        ]}

        graphAccess.execute_query(query, params)