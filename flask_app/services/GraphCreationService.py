from datetime import datetime
import logging
from typing import Dict, List
import json
from uuid import uuid4
from langchain.docstore.document import Document

from flask_app.services.SupabaseService import SupabaseService
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.entities.source_node import sourceNode
from flask_app.services.ChunkService import ChunkService
from flask_app.models.Quiz import QuizQuestion
from flask_app.services.RatelimitService import RatelimitService
from flask_app.services.SimilarityService import SimilarityService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.HelperService import HelperService
from flask_app.services.RedisService import RedisService
from flask_app.extensions import r

from flask_app.src.main import processing_source
from flask_app.constants import COURSEID, NOTE, NOTEID, USERID, GPT_4O_MINI, getGraphKey

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

    @staticmethod
    def create_graph_from_raw_text(  
        noteId: str,
        courseId: str,
        userId: str,
        rawText: str,
        fileName: str,
    ) -> None:
        try:
            chunks = ChunkService.get_text_chunks(rawText)
    
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

    @staticmethod
    def create_graph(
        noteId: str,
        courseId: str,
        userId: str,
        fileName: str,
        import_type: str,
        chunks: List[Document],
    ):
        rateLimitId = RatelimitService.add_rate_limit(userId, NOTE, 1)
        graphAccess: graphDBdataAccess = graphDBdataAccess()

        isPrivate = SupabaseService.isCollegePrivate(courseId=courseId)

        try:
            similarityService = SimilarityService(
                similarity_threshold=0.98, 
                word_edit_distance=5
            )

            similar = similarityService.has_similar_documents(
                courseId=courseId,
                noteId=noteId,
                documents=chunks
            )
            

            if similar and not isPrivate:
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
                graphAccess.update_source_node(sourceNode(noteId=noteId, blockedReason = 'Your note content was detected to be the same as another note in the same course.'))
                SupabaseService.update_note(noteId=noteId, key='blockedReason', value='Your note content was detected to be the same as another note in the same course.')
                RatelimitService.remove_rate_limit(rateLimitId)
                return

            summary = HelperService.get_document_summary(chunks)

            isRelated = SimilarityService.is_related(courseId=courseId, documentSummary=summary, isPrivate=isPrivate)

            if not isRelated['isRelated']:
                graphAccess.update_source_node(sourceNode(noteId=noteId, blockedReason = f'{isRelated["reasoning"]}'))
                SupabaseService.update_note(noteId=noteId, 
                                            key='blockedReason', 
                                            value=f'''
                                            {isRelated["reasoning"]}
                                            ''')
                return None

            obj_source_node = sourceNode(
                file_source=import_type,
                model=GPT_4O_MINI,
                courseId=courseId,
                userId=userId,
                created_at=datetime.now(),
                noteId=noteId,
                summary=summary
            )
            
            graphAccess.create_source_node(obj_source_node)

            chunks = HelperService.clean_chunks(chunks)

            processing_source(
                graphAccess=graphAccess,
                fileName=fileName,
                chunks=chunks,
                userId=userId,
                courseId=courseId,
                noteId=noteId,
                summary=summary
                )
            
            RedisService.setGraph(key=NOTEID, id=noteId)

            logging.info(f"Setting graph for noteId: {noteId}")
            
            RedisService.setGraph(key=COURSEID, id=courseId)

            logging.info(f"Setting graph for courseId: {courseId}")

            SupabaseService.update_note(noteId=noteId, key='updatedAt', value=datetime.now())

        except Exception as e:
            graphAccess: graphDBdataAccess = graphDBdataAccess()
            logging.exception(f'Exception in create_source_node_graph: {e}')
            graphAccess.update_source_node(sourceNode(noteId = noteId, mergeStatus = "error"))
            graphAccess.update_source_node(sourceNode(noteId = noteId, comStatus = "error"))
            graphAccess.update_source_node(sourceNode(noteId = noteId, errorMessage = str(e)))
            SupabaseService.update_note(noteId=noteId, key='graphStatus', value='error')
            RatelimitService.remove_rate_limit(rateLimitId)

    @staticmethod
    def insert_quiz_question(questions: List[QuizQuestion]) -> None:
        graphAccess = graphDBdataAccess()
        
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
            noteIds: q.noteIds,
            difficulty: q.difficulty
        })
        
        WITH question, q
        UNWIND q.topicIds AS topicId
        MATCH (concept:Concept {id: topicId})
        CREATE (concept)-[:HAS_QUESTION]->(question)

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
                'noteIds': json.dumps([{
                    "note_uuid": n['note_uuid'],
                    "document_name": n['document_name']
                } for n in q['noteIds']]),
                'topics': json.dumps([{
                    "name": t['name'], 
                    "uuid": t['uuid']
                } for t in q['topics']]),
                'topicIds': [t['name'] for t in q['topics']],
            } for q in questions
        ]}
        
        graphAccess.execute_query(query, params)

    def insert_summaries(summaries: List[Dict[str, str]]) -> None:
        graphAccess = graphDBdataAccess()
        
        query = """
        UNWIND $summaries AS s
        CREATE (summary:Summary {
            userId: s.userId,
            courseId: s.courseId,
            noteId: s.noteId,
            content: s.content,
            concept: s.concept,
            topicId: s.topicId,
            document_name: s.document_name,
            importance: s.importance
        })

        WITH summary, s
        MATCH (concept:Concept)
        WHERE s.topicId IN concept.uuid
        CREATE (concept)-[:HAS_SUMMARY]->(summary)
        
        RETURN s
        """

        params = {'summaries': [
            {
                USERID: s.get(USERID),
                COURSEID: s.get(COURSEID),
                NOTEID: s.get(NOTEID),
                'content': s.get('content'),
                'concept': s.get('concept'),
                'topicId': s.get('topicId'),
                'document_name': s.get('document_name'),
                'importance': s.get('importance'),
            } for s in summaries
        ]}

        graphAccess.execute_query(query, params)

    @staticmethod
    def insert_question_results(userId: str, results: Dict[str, bool]) -> None:
        graphAccess = graphDBdataAccess()
        
        query = """
        MERGE (u:User {id: $userId})
        WITH u
        UNWIND $results AS result
        MERGE (q:QuizQuestion {id: result.questionId})
        CREATE (u)-[r:ANSWERED]->(q)
        SET r.correct = result.correct,
            r.relationship = CASE WHEN result.correct THEN 'RIGHT' ELSE 'WRONG' END,
            r.timestamp = $timestamp
        """
        
        # Transform the results dictionary into a list of dictionaries
        results_list = [{"questionId": result['uuid'], "correct": result['result']} for result in results]
        
        params = {
            "userId": userId,
            "results": results_list,
            "timestamp": datetime.now().isoformat()
        }

        graphAccess.execute_query(query, params)

    @staticmethod
    def associate_flashcards(
        flashcardId, 
        param, 
        id,
        topic_uuids=None
    ) -> List[Dict[str, str]]:
        graphAccess = graphDBdataAccess()

        logging.info(f"Inserting flashcards for flashcardId: {flashcardId}")

        topic_uuids_list = "[]" if not topic_uuids else "[" + ", ".join(f"'{uuid}'" for uuid in topic_uuids) + "]"

        query = f"""
        MATCH (c:Chunk)-[r:REFERENCES]->(n:Concept)
        WHERE '{id}' IN c.{param}
        AND (size({topic_uuids_list}) = 0 OR ANY(uuid IN {topic_uuids_list} WHERE uuid IN n.uuid))
        WITH n, c, r, rand() AS random
        ORDER BY n.id, random
        WITH n, COLLECT({{chunk: c, rel: r}})[0] AS pair
        SET pair.rel.flashcardId = CASE
            WHEN pair.rel.flashcardId IS NOT NULL THEN pair.rel.flashcardId + ['{flashcardId}']
            ELSE ['{flashcardId}']
        END
        RETURN pair.rel.description AS description, n.id AS nodeId, n.uuid[0] as nodeUuid
        """

        logging.info(query)

        return graphAccess.execute_query(query)
    
    @staticmethod
    def update_note_title(
        noteId: str,
        title: str
    ):
        graphAccess = graphDBdataAccess()

        query = f"""
        MATCH (n:Document)-[:HAS_DOCUMENT]->(c:Chunk)
        WHERE '{noteId}' = n.noteId
        SET n.fileName = '{title}'
        SET c.document_name = '{title}'
        """

        graphAccess.execute_query(query)