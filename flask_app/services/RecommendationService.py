from flask_app.src.graphDB_dataAccess import graphDBdataAccess

class RecommendationService():
    @staticmethod
    def get_recommended_notes_for_user(userId, courseId):
        graphAccess = graphDBdataAccess()

        query = f"""
        MATCH (userNote:Document {{userId: '{userId}', courseId: '{courseId}'}})
        WITH collect(userNote) AS userNotes

        MATCH (otherNote:Document {{courseId: '{courseId}'}})
        WHERE NOT otherNote.userId = '{userId}'

        MATCH (concept:Concept)
        WHERE 
        any(userNote IN userNotes WHERE userNote.noteId IN concept.noteId)
        AND otherNote.noteId IN concept.noteId

        WITH otherNote, count(DISTINCT concept) AS sharedConcepts

        RETURN {{noteId: otherNote.noteId, documentName: otherNote.fileName, createdAt: otherNote.created_at}} as otherNote, sharedConcepts
        ORDER BY sharedConcepts DESC
        LIMIT 10
        """

        result = graphAccess.execute_query(query)

        return result