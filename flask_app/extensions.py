import json
import os
from flask_restx import Api
from flask_cors import CORS
import redis
from supabase import create_client
import runpod
from neo4j.time import DateTime
import fal_client

from dotenv import load_dotenv
load_dotenv()

r = redis.Redis(
  host=os.getenv('REDIS_HOST'),
  port=os.getenv('REDIS_PORT'),
  password=os.getenv('REDIS_PASSWORD'),
  ssl=True
)

api = Api(doc='/docs', title='Notello API', version='1.0', description='An API for Notello')

cors = CORS(resources={r"/*": {"origins": "*"}})
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
runpod.api_key = os.getenv("RUNPOD_API_KEY")

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, DateTime):
            return str(o)

        return json.JSONEncoder.default(self, o)