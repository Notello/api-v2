from flask import Flask

from .extensions import api, cors, supabase, graph
from .routes import init_api

def create_app():
    app = Flask(__name__)

    api.init_app(app)
    cors.init_app(app)

    app.config['NEO4J_GRAPH'] = graph
    app.config['SUPABASE_CLIENT'] = supabase
    
    with app.app_context():
        init_api(api)
        return app
