import logging
from flask import Flask, g

from .extensions import api, cors
from .routes import init_api
from flask_app.services.Neo4jConnection import Neo4jConnection
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.RatelimitService import RatelimitService
from flask_app.src.shared.common_fn import init_indexes

from dotenv import load_dotenv
load_dotenv()

def create_app():
    app = Flask(__name__)

    api.init_app(app)
    cors.init_app(app)

    Neo4jConnection.initialize()
    init_indexes()
    
    with app.app_context():
        ratelimit = SupabaseService.get_rate_limit_values()
        ratelimitdict = RatelimitService.construct_rate_limits_dict(rate_limits=ratelimit)
        g.ratelimit = ratelimitdict
        logging.info(f"Ratelimit: {ratelimitdict}")
        init_api(api)
        return app
