import logging
import os
from flask import request, g
from supabase import create_client, Client
from functools import wraps
from flask_restx import abort

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split()[1]
        
        if not token:
            logging.error("Token is missing")
            abort(401, 'Token is missing')
        
        try:
            response = supabase.auth.get_user(token)
            g.user_id = response.user.id
        except Exception as e:
            logging.exception(f"Error getting user from token: {str(e)}")
            abort(401, 'Token is invalid')
        
        return f(*args, **kwargs)
    
    return decorated