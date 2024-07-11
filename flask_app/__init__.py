import os
from flask import Flask
import runpod

from .extensions import api, cors, supabase, graph
from .routes import init_api

from dotenv import load_dotenv
load_dotenv()

def create_app():
    app = Flask(__name__)

    api.init_app(app)
    cors.init_app(app)

    app.config['NEO4J_GRAPH'] = graph
    app.config['SUPABASE_CLIENT'] = supabase
    app.config['MODEL'] = 'gpt-3.5-turbo-0125'
    app.config['UPDATE_GRAPH_CHUNKS_PROCESSED'] = 10
    app.config['NUMBER_OF_CHUNKS_TO_COMBINE'] = 1
    app.config["RUNPOD_ENDPOINT"] = runpod.Endpoint(os.getenv("RUNPOD_WHISPER_ENDPOINT_ID"))
    
    with app.app_context():
        init_api(api)
        return app
