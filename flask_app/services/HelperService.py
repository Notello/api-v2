import logging
import re
from uuid import UUID
from datetime import datetime
from neo4j.time import DateTime
from pytube import YouTube
import requests

from flask_app.src.document_sources.youtube import get_youtube_transcript
from flask_app.constants import proxy



class HelperService:
    @staticmethod
    def get_youtube_title(youtube_url: str):
        YouTube.proxies = proxy

        # Create a session with the proxy
        session = requests.Session()
        session.proxies = YouTube.proxies

        yt = YouTube(youtube_url, proxies=session.proxies)
        
        return yt.title
    
    @staticmethod
    def validate_uuid4(uuid_string) -> bool:
        """
        Validate that a UUID string is in
        fact a valid uuid4.
        Happily, the uuid module does the actual
        checking for us.
        It is vital that the 'version' kwarg be passed
        to the UUID() call, otherwise any 32-character
        hex string is considered valid.
        """

        logging.info(f"uuid check for: {uuid_string}")
        
        if not type(uuid_string) == str:
            return False

        try:
            val = UUID(uuid_string, version=4)
        except Exception:
            # If it's a value error, then the string 
            # is not a valid hex code for a UUID.
            logging.exception(f"uuid check failed for: {uuid_string}")
            return False

        # If the uuid_string is a valid hex code, 
        # but an invalid uuid4,
        # the UUID.__init__ will convert it to a 
        # valid uuid4. This is bad for validation purposes.

        if val.hex != uuid_string.replace('-', ''):
            logging.exception(f"uuid check failed for: {uuid_string}, hex: {val.hex}")
            return False
        
        print("true")
        return True
    
    @staticmethod
    def validate_all_uuid4(*uuid_strings):
        return all([HelperService.validate_uuid4(uuid_string) for uuid_string in uuid_strings])

    @staticmethod
    def validate_any_uuid4(*uuid_strings):
        return any([HelperService.validate_uuid4(uuid_string) for uuid_string in uuid_strings])
    
    @staticmethod
    def guess_mime_type(file_name):
        try:
            mime_type = None
            if file_name is not None:
                if file_name.endswith('.md'):
                    mime_type = 'text/markdown'
                elif file_name.endswith('.html'):
                    mime_type = 'text/html'
                elif file_name.endswith('.pdf'):
                    mime_type = 'application/pdf'
                else:
                    mime_type = 'application/octet-stream'
            return mime_type
        except Exception as e:
            logging.exception(f'Exception for file: {file_name}, Stack trace: {e}')
            return None

    @staticmethod
    def convert_neo4j_datetime(data):
        if isinstance(data, list):
            return [HelperService.convert_neo4j_datetime(item) for item in data]
        elif isinstance(data, dict):
            return {key: HelperService.convert_neo4j_datetime(value) for key, value in data.items()}
        elif isinstance(data, (DateTime, datetime)):
            logging.info("Datetime")
            type(data)
            logging.info(data.iso_format())
            return data.iso_format()
        else:
            return data
        
    @staticmethod
    def get_video_duration(youtube_url):
        try:
            YouTube.proxies = proxy

            # Create a session with the proxy
            session = requests.Session()
            session.proxies = YouTube.proxies

            yt = YouTube(youtube_url, proxies=session.proxies)

            return yt.length
        except Exception as e:
            logging.exception(f"Error fetching video duration: {e}")
            raise ValueError("Unable to fetch video duration")