import logging
from flask_restx import Namespace, Resource
from werkzeug.datastructures import FileStorage

from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.NoteService import NoteForm, NoteService
from flask_app.services.GraphService import GraphService
from flask_app.services.HelperService import HelperService


api = Namespace('graph')

@api.route('/get-graph-for-course/<string:courseId>')
class GetGraphForCourse(Resource):
    def get(self, courseId):
        try:
            logging.info(f"Get graph for course: {courseId}")

            if not HelperService.validate_uuid4(courseId):
                return {'message': 'Invalid courseId or userId'}, 400
            
            graph = GraphService.get_graph_for_param(key='courseId', value=courseId)

            logging.info(f"Graph, nodes: {len(graph['nodes'])}, relationships: {len(graph['relationships'])}")

            return {'graph': graph}, 200
        except Exception as e:
            message = f" Unable to create source node for source type: youtube, Exception: {e}"
            logging.exception(message)
            return {'message': message}, 400