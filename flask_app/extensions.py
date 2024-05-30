from flask_restx import Api
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db: SQLAlchemy = SQLAlchemy()
api = Api(doc='/docs', title='Notello API', version='1.0', description='An API for Notello')
cors = CORS(resources={r"/*": {"origins": "http://localhost:3000"}})