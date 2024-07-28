import re
from typing import Dict, List
from youtube_transcript_api import YouTubeTranscriptApi


class TimestampService:
    @staticmethod
    def get_youtube_id(
        youtube_url: str,
    ):
        match = re.search(r'(?:v=)([0-9A-Za-z_-]{11})\s*', youtube_url)
        return match.group(1)


    @staticmethod
    def get_youtube_timestamps(
        youtube_url: str,
    ):
        try:
            youtube_id = TimestampService.get_youtube_id(youtube_url)
            return YouTubeTranscriptApi.get_transcript(youtube_id, languages=['en','en-US'])
        except Exception as e:
            message = f"Youtube transcript is not available for youtube Id: {youtube_id}"
            raise Exception(message)