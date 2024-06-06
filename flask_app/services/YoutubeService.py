import logging
import re

from flask_app.src.document_sources.youtube import get_youtube_transcript


class YoutubeService:
    @staticmethod
    def check_url_source(ytUrl: str):
        match = re.search(r'(?:v=)([0-9A-Za-z_-]{11})\s*', ytUrl)
        logging.info(f"match value{match}")

        transcript = get_youtube_transcript(match.group(1))

        if transcript==None or len(transcript)==0:
            message = f"Youtube transcript is not available for : {ytUrl}"
            raise Exception(message)

        return transcript