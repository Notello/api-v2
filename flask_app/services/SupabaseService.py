import logging
from supabase import Client
from werkzeug.datastructures import FileStorage
from flask import current_app

supabase: Client = current_app.config['SUPABASE_CLIENT']

class SupabaseService:

    @staticmethod
    def add_note(
        courseId: str, 
        userId: str, 
        form: str, 
        status: str = 'pending',
        content: str = '',
        sourceUrl: str = ''
    ) -> list:
        return supabase.table('webapp-v2_note').insert({
            'courseId': courseId,
            'userId': userId,
            'form': form,
            'contentStatus': status,
            'rawContent': content,
            'sourceUrl': sourceUrl,
        }).execute().data
    
    @staticmethod
    def upload_file(
        file: FileStorage, 
        fileName: str, 
        bucketName: str
    ):
        file_content = file.read()

        response = supabase.storage.from_(bucketName).upload(
            fileName,
            file_content,
            file_options={'content-type': 'audio/*'}
        )

        logging.info(f'Uploaded file: {fileName} to bucket: {bucketName}')
        return response.json()
    
    @staticmethod
    def update_note(noteId: str, key: str, value: str):
        return supabase.table('webapp-v2_note').update({key: value}).eq('id', noteId).execute().data
