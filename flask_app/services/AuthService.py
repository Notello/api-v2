import logging
import os
from supabase import Client, create_client

from flask_app.constants import NOTE_TABLE_NAME, USER_CLASS_TABLE_NAME


supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))


class AuthService():

    @staticmethod
    def is_super_admin(user_id):
        return supabase.auth.get_user(user_id).data['is_super_admin']

    @staticmethod
    def can_edit_course(user_id, course_id):
        course = supabase.table(USER_CLASS_TABLE_NAME).select('*').eq('user_id', user_id).eq('course_id', course_id).execute().data

        return len(course) != 0 and (course[0]['isOwner'] or AuthService.is_super_admin(user_id))
    
    @staticmethod
    def can_edit_user(user_id, user_id_to_edit):
        return AuthService.is_matching_user(user_id, user_id_to_edit) or AuthService.is_super_admin(user_id)
    
    @staticmethod
    def is_matching_user(user_id, user_id_to_match):
        return user_id == user_id_to_match
    
    @staticmethod
    def is_authed_for_userId(reqUserId, user_id_to_auth):
        return AuthService.is_matching_user(reqUserId, user_id_to_auth) or AuthService.is_super_admin(reqUserId)
    
    @staticmethod
    def can_edit_note(user_id, note_id):
        note = supabase.table(NOTE_TABLE_NAME).select('*').eq('id', note_id).execute().data

        return len(note) != 0 and (AuthService.is_matching_user(user_id, note[0]['userId']) or AuthService.is_super_admin(user_id))