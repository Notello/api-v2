import os
from flask import request
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
            abort(401, 'Token is missing')
        
        try:
            user = supabase.auth.get_user(token)
        except Exception as e:
            abort(401, 'Token is invalid')
        
        return f(*args, **kwargs)
    
    return decorated