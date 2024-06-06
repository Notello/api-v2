import logging
import re
from uuid import UUID


from flask_app.src.document_sources.youtube import get_youtube_transcript


class HelperService:
    @staticmethod
    def check_url_source(ytUrl: str):
        match = re.search(r'(?:v=)([0-9A-Za-z_-]{11})\s*', ytUrl)
        logging.info(f"match value{match}")

        transcript = get_youtube_transcript(match.group(1))

        if transcript==None or len(transcript)==0:
            message = f"Youtube transcript is not available for : {ytUrl}"
            logging.exception(message)
            raise Exception(message)

        return transcript
    
    @staticmethod
    def validate_uuid4(*uuid_strings):

        """
        Validate that a UUID string is in
        fact a valid uuid4.
        Happily, the uuid module does the actual
        checking for us.
        It is vital that the 'version' kwarg be passed
        to the UUID() call, otherwise any 32-character
        hex string is considered valid.
        """

        for uuid_string in uuid_strings:
            logging.info(f"uuid check for: {uuid_string}")
            try:
                val = UUID(uuid_string, version=4)
            except ValueError:
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