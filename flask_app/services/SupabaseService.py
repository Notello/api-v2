from datetime import datetime, timedelta, UTC
from io import BytesIO
import logging
import os
from typing import Dict, List
from supabase import Client, create_client
from flask_app.services.HelperService import HelperService

from flask_app.constants import COURSEID, ID, NOTE_TABLE_NAME, NOTEID, PROFILE_TABLE_NAME, QUIZ_TABLE_NAME, RATE_LIMIT_TABLE_NAME, RATE_LIMIT_VALUES_TABLE_NAME, SUPAID, TOPIC_SUMMARY_TABLE_NAME, USERID, COURSE_TABLE_NAME

supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

class SupabaseService:

    @staticmethod
    def add_note(
        courseId: str, 
        userId: str, 
        form: str, 
        status: str,
        content: str = '',
        sourceUrl: str = '',
        title: str = '',
        noteId: str = None
    ) -> list:
        try:
            if not HelperService.validate_all_uuid4(courseId, userId):
                logging.error(f'Invalid courseId: {courseId}, userId: {userId}')
                return []

            out = None

            logging.info(f"noteId: {noteId}")

            if noteId:
                out = supabase.table(NOTE_TABLE_NAME).insert({
                    ID: noteId,
                    COURSEID: courseId,
                    USERID: userId,
                    'form': form,
                    'contentStatus': status,
                    'rawContent': content,
                    'sourceUrl': sourceUrl,
                    'title': title,
                }).execute().data
            else:
                out = supabase.table(NOTE_TABLE_NAME).insert({
                    COURSEID: courseId,
                    USERID: userId,
                    'form': form,
                    'contentStatus': status,
                    'rawContent': content,
                    'sourceUrl': sourceUrl,
                    'title': title,
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
    def delete_file(fileId: str, bucketName: str):
        try:
            if not HelperService.validate_all_uuid4(fileId):
                logging.error(f'Invalid fileId: {fileId}')
                return None

            logging.info(f'Deleting file {fileId}')

            return supabase.storage.from_(bucketName).remove(fileId)
        except Exception as e:
            logging.exception(f'Exception in delete_file: {e}')
            return None
    
    @staticmethod
    def update_note(noteId: str, key: str, value: str):
        try:
            if not HelperService.validate_all_uuid4(noteId):
                logging.error(f'Invalid noteId: {noteId}')
                return None

            logging.info(f'Updating note {noteId} with key {key} and value {value}')
            return supabase.table(NOTE_TABLE_NAME).update({
                str(key): str(value)
                }).eq('id', str(noteId)).execute().data
        except Exception as e:
            logging.exception(f'Exception in update_note: {e}')
            return None
    
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
    
    @staticmethod
    def param_id_exists(param: str, id: str) -> bool:
        if not HelperService.validate_all_uuid4(id) :
            logging.error(f'Invalid {param} id: {id}')
            return False
        
        out = False
        
        if param == 'courseId':
            out = supabase.table(COURSE_TABLE_NAME).select('*').eq(ID, id).execute().data != []
        elif param == 'userId':
            out = supabase.table(PROFILE_TABLE_NAME).select('*').eq(SUPAID, id).execute().data != []
        elif param == 'noteId':
            out = supabase.table(NOTE_TABLE_NAME).select('*').eq(ID, id).execute().data != []
        

        logging.info(f'Param {param}, id {id} exists: {out}')
        return out
    
    @staticmethod
    def delete_note(noteId: str, bucketName: str):
        if not HelperService.validate_all_uuid4(noteId):
            logging.error(f'Invalid noteId: {noteId}')
            return None

        supabase.table(NOTE_TABLE_NAME).delete().eq('id', str(noteId)).execute().data

        if bucketName:
            SupabaseService.delete_file(fileId=noteId, bucketName=bucketName)
    
    @staticmethod
    def delete_course(courseId: str):
        if not HelperService.validate_all_uuid4(courseId):
            logging.error(f'Invalid courseId: {courseId}')
            return None

        return supabase.table(COURSE_TABLE_NAME).delete().eq('id', str(courseId)).execute().data
    
    @staticmethod
    def delete_user(userId: str):
        if not HelperService.validate_all_uuid4(userId):
            logging.error(f'Invalid userId: {userId}')
            return None
        
        supabase.auth.admin.delete_user(userId)
    
    @staticmethod
    def get_noteIds_for_course(courseId: str) -> List[str]:
        if not HelperService.validate_all_uuid4(courseId):
            logging.error(f'Invalid courseId: {courseId}')
            return []

        return supabase.table(NOTE_TABLE_NAME).select('*').eq('courseId', str(courseId)).execute().data

    @staticmethod
    def get_notes_for_user(userId: str) -> List[str]:
        if not HelperService.validate_all_uuid4(userId):
            logging.error(f'Invalid userId: {userId}')
            return []

        return supabase.table(NOTE_TABLE_NAME).select('*').eq('userId', str(userId)).execute().data
    
    @staticmethod
    def get_user(email: str, password: str) -> dict:
        credentials={"email": email, "password": password}
        return supabase.auth.sign_in_with_password(credentials)
    
    @staticmethod
    def get_user_type(userId: str) -> str:
        if not HelperService.validate_all_uuid4(userId):
            logging.error(f'Invalid userId: {userId}')
            return ''

        user = supabase.table(PROFILE_TABLE_NAME).select('*').eq(SUPAID, str(userId)).execute().data

        if not user:
            return ''

        return user[0]['accountType']
    
    @staticmethod
    def get_rate_limit(userId: str, type: str):
        if not HelperService.validate_all_uuid4(userId):
            logging.error(f'Invalid userId: {userId}')
            return {}

        now = datetime.now(UTC)

        # Fetch data for the last 30 days
        result = supabase.table(RATE_LIMIT_TABLE_NAME)\
            .select('created_at, count')\
            .eq('type', str(type))\
            .eq('userId', str(userId))\
            .gte('created_at', now - timedelta(days=30))\
            .execute()

        return result.data

    @staticmethod
    def get_rate_limit_values(type: str, userType: str) -> dict:
        return supabase.table(RATE_LIMIT_VALUES_TABLE_NAME).select('*').eq('type', str(type)).eq('userType', str(userType)).execute().data
    
    @staticmethod
    def add_rate_limit(userId: str, type: str, count: int):
        if not HelperService.validate_all_uuid4(userId):
            logging.error(f'Invalid userId: {userId}')
            return None
        
        return supabase.table(RATE_LIMIT_TABLE_NAME).insert({
            'userId': str(userId),
            'type': str(type),
            'count': count
        }).execute().data

    @staticmethod
    def delete_rate_limit(rateLimitId: str):
        if not HelperService.validate_all_uuid4(rateLimitId):
            logging.error(f'Invalid rateLimitId: {rateLimitId}')
            return None
        
        return supabase.table(RATE_LIMIT_TABLE_NAME).delete().eq('id', str(rateLimitId)).execute().data
    
    @staticmethod
    def get_note_type(noteId: str):
        if not HelperService.validate_all_uuid4(noteId):
            logging.error(f'Invalid noteId: {noteId}')
            return None

        out = supabase.table(NOTE_TABLE_NAME).select('*').eq(ID, noteId).execute().data

        if not out:
            return None

        return out[0]['form']