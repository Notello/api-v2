import logging
from flask_restx import Namespace, Resource

from flask_app.services.QuizService import QuizService
from flask_app.services.HelperService import HelperService
from flask_app.services.GraphQueryService import GraphQueryService
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.ContextAwareThread import ContextAwareThread
from flask_app.services.SummaryService import SummaryService

api = Namespace('summary')


create_topic_summary_parser = api.parser()

create_topic_summary_parser.add_argument('userId', location='form',
                        type=str, required=True,
                        help='Supabase ID of the user')
create_topic_summary_parser.add_argument('courseId', location='form',
                        type=str, required=True,
                        help='Course ID associated with the summary')
create_topic_summary_parser.add_argument('topics', location='form', action='split')

@api.expect(create_topic_summary_parser)
@api.route('/generate-topic-summary')
class GenerateTopicSummary(Resource):
    def post(self):
        args = create_topic_summary_parser.parse_args()
        userId = args.get('userId', None)
        courseId = args.get('courseId', None)
        topics = args.get('topics', None)

        if topics is None:
            topics = []

        if (
            not HelperService.validate_all_uuid4(userId, courseId)
            or len(topics) == 0
        ):
            return {'message': 'Must have userId, courseId, and at least one topic'}, 400
        
        return {'message': 'Not implemented yet'}, 400

create_note_summary_parser = api.parser()

create_note_summary_parser.add_argument('userId', location='form',
                        type=str, required=True,
                        help='Supabase ID of the user')
create_note_summary_parser.add_argument('courseId', location='form',
                        type=str, required=True,
                        help='Course ID associated with the summary')
create_note_summary_parser.add_argument('noteId', location='form',
                        type=str, required=True,
                        help='Note ID associated with the summary')    

@api.expect(create_note_summary_parser)
@api.route('/generate-note-summary')
class GenerateNoteSummary(Resource):
    def post(self):
        args = create_note_summary_parser.parse_args()
        userId = args.get('userId', None)
        courseId = args.get('courseId', None)
        noteId = args.get('noteId', None)

        if (
            not HelperService.validate_all_uuid4(userId, courseId, noteId)
        ):
            return {'message': 'Must have userId, courseId, and noteId'}, 400
          
        SummaryService.generate_note_summary(
            userId=userId, 
            courseId=courseId,
            noteId=noteId,
            specifierParam='noteId'
            )