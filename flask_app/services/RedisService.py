import json

from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.constants import getGraphKey
from flask_app.extensions import r

class RedisService:
    @staticmethod
    def setGraph(key, id):
        nodes, relationships = GraphQueryService.get_graph_for_param(key=key, value=id)
        r.set(getGraphKey(id), json.dumps({'nodes': nodes, 'relationships': relationships}))