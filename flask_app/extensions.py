import json
import os
from flask_restx import Api
from flask_cors import CORS
from supabase import create_client
import runpod
from datetime import datetime
from neo4j.time import DateTime

from dotenv import load_dotenv
load_dotenv()

from flask_app.src.shared.common_fn import create_graph_database_connection

api = Api(doc='/docs', title='Notello API', version='1.0', description='An API for Notello')

ENV_MAP = {
    'dev': {
        'allow': "*",
        'NEO4J_URI': os.getenv('NEO4J_URI'),
        'NEO4J_USERNAME': os.getenv('NEO4J_USERNAME'),
        'NEO4J_PASSWORD': os.getenv('NEO4J_PASSWORD'),
        'NEO4J_DATABASE': os.getenv('NEO4J_DATABASE')
    },
    'prod': {
        'allow': ["https://notello.ai", "https://www.notello.ai"],
        'NEO4J_URI': os.getenv('PROD_NEO4J_URI'),
        'NEO4J_USERNAME': os.getenv('PROD_NEO4J_USERNAME'),
        'NEO4J_PASSWORD': os.getenv('PROD_NEO4J_PASSWORD'),
        'NEO4J_DATABASE': os.getenv('PROD_NEO4J_DATABASE')
    }
}

cors = CORS(resources={r"/*": {"origins": ENV_MAP[os.getenv('ENV_TYPE')]['allow']}})


supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
graph = create_graph_database_connection(
    ENV_MAP[os.getenv('ENV_TYPE')]['NEO4J_URI'], 
    ENV_MAP[os.getenv('ENV_TYPE')]['NEO4J_USERNAME'], 
    ENV_MAP[os.getenv('ENV_TYPE')]['NEO4J_PASSWORD'], 
    ENV_MAP[os.getenv('ENV_TYPE')]['NEO4J_DATABASE']
)
runpod.api_key = os.getenv("RUNPOD_API_KEY")

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, DateTime):
            return str(o)

        return json.JSONEncoder.default(self, o)  
