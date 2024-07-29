import logging
from flask_restx import Namespace, Resource

from flask_app.services.QuizService import QuizService
from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.SummaryService import SummaryService
from flask_app.constants import COURSEID, NOTEID, USERID

api = Namespace('summary')


create_topic_summary_parser = api.parser()

create_topic_summary_parser.add_argument(USERID, location='form',
                        type=str, required=True,
                        help='Supabase ID of the user')
create_topic_summary_parser.add_argument(COURSEID, location='form',
                        type=str, required=True,
                        help='Course ID associated with the summary')

@api.expect(create_topic_summary_parser)
@api.route('/generate-topic-summary/<string:topicId>')
class GenerateTopicSummary(Resource):
    def post(self, topicId):
        args = create_topic_summary_parser.parse_args()
        userId = args.get(USERID, None)
        courseId = args.get(COURSEID, None)

        if (not HelperService.validate_all_uuid4(userId, courseId, topicId)):
            return {'message': 'Must have userId, courseId, and topicId'}, 400
        
        SummaryService.generate_topic_summary(
            userId=userId, 
            courseId=courseId,
            topicId=topicId
            )
        
        return {'message': 'Summary generating'}, 200

create_note_summary_parser = api.parser()

create_note_summary_parser.add_argument(USERID, location='form',
                        type=str, required=True,
                        help='Supabase ID of the user')
create_note_summary_parser.add_argument(COURSEID, location='form',
                        type=str, required=True,
                        help='Course ID associated with the summary')  

@api.expect(create_note_summary_parser)
@api.route('/generate-note-summary/<string:noteId>')
class GenerateNoteSummary(Resource):
    def post(self, noteId):
        args = create_note_summary_parser.parse_args()
        userId = args.get(USERID, None)
        courseId = args.get(COURSEID, None)

        if (
            not HelperService.validate_all_uuid4(userId, courseId, noteId)
        ):
            return {'message': 'Must have userId, courseId, and noteId'}, 400
          
        SummaryService.generate_note_summary(
            userId=userId, 
            courseId=courseId,
            noteId=noteId,
            specifierParam=NOTEID
            )
    
@api.route('/get-summary-for/<string:param>/<string:id>')
class GetSummaryFor(Resource):
    def get(self, param, id):
        return GraphQueryService.get_summary_for_param(param=param, id=id)
    
@api.route('/get-summary-for-topic/<string:topicId>')
class GetSummaryForTopic(Resource):
    def get(self, topicId):
        return GraphQueryService.get_topic_summary(uuid=topicId)