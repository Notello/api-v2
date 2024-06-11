from json import JSONEncoder
import os
from flask_restx import Api
from flask_cors import CORS
from supabase import create_client
import runpod
from neo4j.time import DateTime as Neo4jDateTime
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

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
runpod.api_key = os.getenv("RUNPOD_API_KEY")

class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (Neo4jDateTime, datetime)):
            return obj.iso_format()
        return super().default(obj)

