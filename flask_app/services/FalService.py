import logging
import os
import tempfile
from werkzeug.datastructures import FileStorage

import fal_client

class FalService:
    @staticmethod
    def transcribe_audio(audio_file_path: str):
        try:
            file_url = fal_client.upload_file(audio_file_path)
            output = fal_client.run('fal-ai/wizper', arguments={"audio_url": file_url})

            return FalService.get_fal_timestamps(output)
        except Exception as e:
            logging.exception(f"Error transcribing audio: {str(e)}")
            return None
    
    @staticmethod
    def get_fal_timestamps(output):
        transcript = []

        for entry in output['chunks']:
            transcript.append({
                'text': entry['text'],
                'start': entry['timestamp'][0]
            })

        return transcript