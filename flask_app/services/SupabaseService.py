from io import BytesIO
import logging
from supabase import Client
from flask import current_app

supabase: Client = current_app.config['SUPABASE_CLIENT']

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
            out = supabase.table('webapp-v2_note').insert({
                'courseId': courseId,
                'userId': userId,
                'form': form,
                'contentStatus': status,
                'rawContent': content,
                'sourceUrl': sourceUrl,
            }).execute()

            logging.info(f'Note added successfully for courseId: {courseId}, userId: {userId}, form: {form}, data: {out.data}')

            return out.data
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
        logging.info(f'Updating note {noteId} with key {key} and value {value}')
        return supabase.table('webapp-v2_note').update({key: value}).eq('id', noteId).execute().data
