import os
from flask_restx import Api
from flask_cors import CORS
from supabase import create_client

from flask_app.src.shared.common_fn import create_graph_database_connection

api = Api(doc='/docs', title='Notello API', version='1.0', description='An API for Notello')
cors = CORS(resources={r"/*": {"origins": "http://localhost:3000"}})
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
graph = create_graph_database_connection(
    os.getenv('NEO4J_URI'), 
    os.getenv('NEO4J_USERNAME'), 
    os.getenv('NEO4J_PASSWORD'),
    os.getenv('NEO4J_DATABASE')
)
