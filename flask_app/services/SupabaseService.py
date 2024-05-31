from flask import current_app
from supabase import Client

supabase: Client = current_app.config['SUPABASE_CLIENT']

class SupabaseService:
    
    @staticmethod
    def add_note(
        courseId: str, 
        userId: str, 
        form: str, 
        status: str = 'PENDING',
        content: str = ''
    ):
        return supabase.table('webapp-v2_note').insert({
            'courseId': courseId,
            'userId': userId,
            'form': form,
            'status': status,
            'content': content
        }).execute().data