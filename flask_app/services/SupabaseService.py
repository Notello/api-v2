from io import BytesIO
import logging
import os
from typing import List
from supabase import Client, create_client
from flask_app.services.HelperService import HelperService

from flask_app.constants import COURSEID, NOTE_TABLE_NAME, NOTEID, QUIZ_QUESTION_TABLE_NAME, QUIZ_TABLE_NAME, TOPIC_SUMMARY_TABLE_NAME, USERID

supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

class SupabaseService:

    @staticmethod
    def add_note(
        courseId: str, 
        userId: str, 
        form: str, 
        status: str,
        content: str = '',
        sourceUrl: str = ''
    ) -> list:
        try:
            if not HelperService.validate_all_uuid4(courseId, userId):
                logging.error(f'Invalid courseId: {courseId}, userId: {userId}')
                return []

            out = supabase.table(NOTE_TABLE_NAME).insert({
                COURSEID: courseId,
                USERID: userId,
                'form': form,
                'contentStatus': status,
                'rawContent': content,
                'sourceUrl': sourceUrl,
            }).execute().data

            logging.info(f'Note added successfully for courseId: {courseId}, userId: {userId}, form: {form}, data: {out}')

            return out
        except Exception as e:
            logging.exception(f'Exception in add_note: {e}')
            return []
    
    @staticmethod
    def upload_file(
        file: BytesIO,
        fileName: str, 
        bucketName: str,
        contentType: str
    ) -> str | None:
        try:
            response = supabase.storage.from_(bucketName).upload(
                fileName,
                file,
                file_options={'content-type': contentType}
            )

            json = response.json()
            SupabaseService.update_note(fileName, 'sourceUrl', "file url placeholder")
            logging.info(f'Uploaded file: {fileName} to bucket: {bucketName}')
            logging.info(f'File ID: {json["Id"]}')
            return json['Id']
        except Exception as e:
            logging.exception(f'Exception in upload_file: {e}')
            return None
    
    @staticmethod
    def update_note(noteId: str, key: str, value: str):
        if not HelperService.validate_all_uuid4(noteId):
            logging.error(f'Invalid noteId: {noteId}')
            return None

        logging.info(f'Updating note {noteId} with key {key} and value {value}')
        return supabase.table(NOTE_TABLE_NAME).update({
            str(key): str(value)
            }).eq('id', str(noteId)).execute().data
    
    @staticmethod
    def create_quiz(
        noteId: str, 
        courseId: str, 
        userId: str,
        difficulty: int,
        numQuestions: int,
        ):
        if not HelperService.validate_all_uuid4(courseId, userId):
            logging.error(f'Invalid noteId: {noteId}, courseId: {courseId}, userId: {userId}')
            return None

        quiz = supabase.table(QUIZ_TABLE_NAME).insert({
            NOTEID: noteId,
            COURSEID: courseId,
            USERID: userId,
            'difficulty': difficulty,
            'num_questions': numQuestions,
        }).execute().data

        if len(quiz) == 0:
            return None

        quizId = quiz[0]['id']

        logging.info(f'Quiz created successfully for courseId: {courseId}, userId: {userId}, noteId: {noteId}')

        return quizId
    
    @staticmethod
    def update_quiz(
        quizId: str,
        key: str,
        value: str
    ) -> List[str]:
        if not HelperService.validate_all_uuid4(quizId):
            logging.error(f'Invalid quizId: {quizId}')
            return []

        return supabase.table(QUIZ_TABLE_NAME).update({
            str(key): str(value)
            }).eq('id', str(quizId)).execute().data
    
    @staticmethod
    def add_summary(
        topicId: str
    ) -> List[str]:
        if not HelperService.validate_all_uuid4(topicId):
            logging.error(f'Invalid noteId: {topicId}')
            return []

        return supabase.table(TOPIC_SUMMARY_TABLE_NAME).insert({
            'topicId': str(topicId)
        }).execute().data
    
    @staticmethod
    def update_summary(
        summaryId: str,
        key: str,
        value: str
    ):
        if not HelperService.validate_all_uuid4(summaryId):
            logging.error(f'Invalid summaryId: {summaryId}')
            return None

        logging.info(f'Updating summary {summaryId} with key {key}')
        return supabase.table(TOPIC_SUMMARY_TABLE_NAME).update({
            str(key): str(value)
            }).eq('id', str(summaryId)).execute().data