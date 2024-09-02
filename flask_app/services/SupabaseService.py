from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import logging
import os
from typing import Dict, List
from supabase import Client, create_client
from flask_app.services.HelperService import HelperService

from flask_app.constants import *

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
            if hasattr(e, 'response'):
                logging.error(f'Response content: {e.response.content}')
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
            'difficulty': difficulty,
        }).execute().data

        if len(quiz) == 0:
            return None

        quizId = quiz[0]['id']

        logging.info(f'Quiz created successfully for courseId: {courseId}, userId: {userId}, noteId: {noteId}')

        return quizId
    
    @staticmethod
    def create_flashcards(
        courseId: str, 
        noteId: str, 
        userId: str,
        setName: str
    ):
        if not HelperService.validate_all_uuid4(courseId, userId):
            logging.error(f'Invalid courseId: {courseId}, userId: {userId}')
            return None

        flashcard = supabase.table(FLASHCARD_TABLE_NAME).insert({
            NOTEID: noteId,
            COURSEID: courseId,
            USERID: userId,
            'setName': setName
        }).execute().data

        if len(flashcard) == 0:
            return None

        logging.info(f'Flashcard created successfully for courseId: {courseId}, userId: {userId}, noteId: {noteId}')

        return flashcard[0]['id']
    
    @staticmethod
    def update_flashcards(
        flashcardId: str,
        key: str,
        value: str
    ):
        if not HelperService.validate_all_uuid4(flashcardId):
            logging.error(f'Invalid flashcardId: {flashcardId}')
            return None
        
        return supabase.table(FLASHCARD_TABLE_NAME).update({
            str(key): str(value)
            }).eq('id', str(flashcardId)).execute().data

    
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
        elif param == 'quizId':
            out = supabase.table(QUIZ_TABLE_NAME).select('*').eq(ID, id).execute().data != []
        

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

        now = datetime.now(timezone.utc)

        result = supabase.table(RATE_LIMIT_TABLE_NAME)\
            .select('created_at, count, userType')\
            .eq('type', str(type))\
            .eq('userId', str(userId))\
            .gte('created_at', now - timedelta(days=30))\
            .execute()

        return result.data

    @staticmethod
    def get_rate_limit_values() -> dict:
        return supabase.table(RATE_LIMIT_VALUES_TABLE_NAME).select('*').execute().data
    
    @staticmethod
    def add_rate_limit(userId: str, type: str, count: int, userType: str):
        if not HelperService.validate_all_uuid4(userId):
            logging.error(f'Invalid userId: {userId}')
            return None
        
        return supabase.table(RATE_LIMIT_TABLE_NAME).insert({
            'userId': str(userId),
            'type': str(type),
            'count': count,
            'userType': str(userType)
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
    
    @staticmethod
    def isCollegePrivate(courseId: str):
        if not HelperService.validate_all_uuid4(courseId):
            logging.error(f'Invalid courseId: {courseId}')
            return None

        out = supabase.table(COURSE_TABLE_NAME).select('*').eq(ID, courseId).execute().data

        if not out:
            return None

        collegeId = out[0]['collegeId']

        if not HelperService.validate_all_uuid4(collegeId):
            logging.error(f'Invalid collegeId: {collegeId}')
            return None

        out = supabase.table(COLLEGE_TABLE_NAME).select('*').eq(ID, collegeId).execute().data

        if not out:
            return None

        return out[0]['isPrivate']
    
    @staticmethod
    def create_chat_room(user_id):
        if not HelperService.validate_all_uuid4(user_id):
            logging.error(f'Invalid userId: {user_id}')
            return None
        
        chatRoom = supabase.table(CHAT_TABLE_NAME).insert({
            'ownerId': str(user_id)
        }).execute().data

        if not chatRoom:
            return None

        return chatRoom[0]['id']
    
    @staticmethod
    def add_chat_message(chat_room_id, user_id, message):
        if not HelperService.validate_all_uuid4(chat_room_id):
            logging.error(f'Invalid chat_room_id: {chat_room_id}, user_id: {user_id}')
            return None

        message = supabase.table(CHAT_MESSAGE_TABLE_NAME).insert({
            'chatId': str(chat_room_id),
            'userId': user_id,
            'content': str(message)
        }).execute().data

        if not message:
            return None

        return message[0]['id']
    
    @staticmethod
    def edit_chat_message(message_id, message):
        if not HelperService.validate_all_uuid4(message_id):
            logging.error(f'Invalid message_id: {message_id}')
            return None

        return supabase.table(CHAT_MESSAGE_TABLE_NAME).update({
            'content': str(message)
        }).eq('id', str(message_id)).execute().data
    
    @staticmethod
    def get_chat_history(chat_room_id):
        if not HelperService.validate_all_uuid4(chat_room_id):
            logging.error(f'Invalid chat_room_id: {chat_room_id}')
            return None

        messages = supabase.table(CHAT_MESSAGE_TABLE_NAME).select('*').eq('chatId', str(chat_room_id)).order('created_at', desc=False).execute().data

        logging.info(f"Chat messages: {messages}")

        messages.pop()

        if len(messages) > 10:
            messages = messages[-10:]

        return messages
    
    @staticmethod
    def get_annotated_messages(chat_room_id):
        messages = SupabaseService.get_chat_history(chat_room_id=chat_room_id)

        if not messages:
            return None
        
        return [f"{'Human' if message['userId'] is not None else 'Bot'} Message: {json.loads(message['content'])['message']}" for message in messages]
    
    @staticmethod
    def get_chat_text(chat_room_id):
        messages = SupabaseService.get_chat_history(chat_room_id=chat_room_id)

        if not messages:
            return None
        
        return [json.loads(message['content'])['message'] for message in messages]
    
    @staticmethod
    def get_course_description(courseId: str) -> str:
        if not HelperService.validate_all_uuid4(courseId):
            logging.error(f'Invalid courseId: {courseId}')
            return None

        out = supabase.table(COURSE_TABLE_NAME).select('*').eq(ID, courseId).execute().data

        if not out:
            return None

        return {
            "description": out[0].get('description'),
            "courseNumber": out[0].get('courseNumber'),
            "name": out[0].get('name'),
        }
    
    @staticmethod
    def user_has_flashcard(userId: str, param: str, id: str) -> bool:
        if not HelperService.validate_all_uuid4(userId, id):
            logging.error(f'Invalid userId: {userId}, param: {param}, id: {id}')
            return False

        out = supabase.table(FLASHCARD_TABLE_NAME).select('*').eq(USERID, str(userId)).eq(param, str(id)).execute().data

        if not out:
            return False

        return True