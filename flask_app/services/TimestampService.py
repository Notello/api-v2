import re
from typing import Dict, List
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from flask_app.constants import ProxyRotator


class TimestampService:
    @staticmethod
    def get_youtube_id(
        youtube_url: str,
    ):
        match = re.search(r'(?:v=)([0-9A-Za-z_-]{11})\s*', youtube_url)
        return match.group(1)


    @staticmethod
    def get_youtube_timestamps(youtube_url: str):
        proxy_rotator = ProxyRotator()

        for _ in range(10):
            try:
                youtube_id = TimestampService.get_youtube_id(youtube_url)
                proxy = proxy_rotator.get_proxy_info()
                return YouTubeTranscriptApi.get_transcript(youtube_id, languages=['en', 'en-US'], proxies=proxy)
            except Exception as e:
                proxy_rotator.rotate_proxy_port()
                continue

        # If all attempts fail, raise an exception
        message = f"Youtube transcript is not available for youtube URL: {youtube_url}"
        raise Exception(message)