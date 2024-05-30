from flask import Flask

from .extensions import api, cors, db
from .routes import init_api

def create_app():
    app = Flask(__name__)

    api.init_app(app)
    cors.init_app(app)
    # db.init_app(app)

    with app.app_context():
        init_api(api)
        return app
