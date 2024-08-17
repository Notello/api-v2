from flask import Flask

from .extensions import api, cors
from .routes import init_api
from flask_app.services.Neo4jConnection import Neo4jConnection
from flask_app.src.shared.common_fn import init_indexes

from dotenv import load_dotenv
load_dotenv()

def create_app():
    app = Flask(__name__)

    api.init_app(app)
    cors.init_app(app)

    Neo4jConnection.initialize()

    app.config['MODEL'] = 'gpt-3.5-turbo-0125'
    app.config['UPDATE_GRAPH_CHUNKS_PROCESSED'] = 10
    app.config['NUMBER_OF_CHUNKS_TO_COMBINE'] = 1
    
    with app.app_context():
        init_api(api)
        return app
