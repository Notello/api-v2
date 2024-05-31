import os
from flask_restx import Api
from flask_cors import CORS
from supabase import create_client

api = Api(doc='/docs', title='Notello API', version='1.0', description='An API for Notello')
cors = CORS(resources={r"/*": {"origins": "http://localhost:3000"}})
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))