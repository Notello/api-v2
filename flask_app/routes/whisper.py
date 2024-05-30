from flask_restx import Resource, Namespace, fields
from werkzeug.datastructures import FileStorage

api = Namespace('')

file_upload = api.parser()
file_upload.add_argument('file', location='files',
                        type=FileStorage, required=True,
                        help='Audio file to be transcribed')
file_upload.add_argument('keywords', location='form', 
                        type=str, required=False,
                        help='Space-separated keywords to enhance transcription accuracy')

transcription_input = api.model('TranscriptionInput', {
    'text': fields.String()
})

@api.expect(file_upload)
@api.expect(transcription_input)
@api.route('/create-audio-note')
class Whisper(Resource):
    def post(self):
        args = file_upload.parse_args()
        print(args)
        audio_file = args.get('file', None)
        keywords = args.get('keywords', None)
        return 'Whisper'