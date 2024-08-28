import logging
import re
from typing import List
from uuid import UUID
from datetime import datetime
from neo4j.time import DateTime
from pytube import YouTube
from langchain.prompts import ChatPromptTemplate
from langchain.docstore.document import Document

from flask_app.constants import GPT_4O_MINI, ProxyRotator
from flask_app.src.shared.common_fn import get_llm

class HelperService:
    @staticmethod
    def get_youtube_title(youtube_url: str):
        proxy_rotator = ProxyRotator()

        for _ in range(10):
            try:
                proxy = proxy_rotator.get_proxy_info()
                return YouTube(youtube_url, proxies=proxy).title.strip()
            except Exception as e:
                proxy_rotator.rotate_proxy_port()
                continue

        logging.exception(f"Error fetching youtube title for URL: {youtube_url}")
        return "Youtube Video"
    
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
                elif file_name.endswith('.mp3'):
                    mime_type = 'audio/mpeg'
                elif file_name.endswith('.wav'):
                    mime_type = 'audio/wav'
                elif file_name.endswith('.ogg'):
                    mime_type = 'audio/ogg'
                elif file_name.endswith('.m4a'):
                    mime_type = 'audio/mp4'
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
    def get_video_duration(youtube_url: str):
        proxy_rotator = ProxyRotator()

        for _ in range(10):
            try:
                proxy = proxy_rotator.get_proxy_info()
                return YouTube(youtube_url, proxies=proxy).length
            except Exception as e:
                proxy_rotator.rotate_proxy_port()
                continue

        logging.exception(f"Error fetching video duration for URL: {youtube_url}")
        return 0
        

    @staticmethod
    def get_document_summary(
        chunks: List[Document],
    ):
        text = "\n".join([chunk.page_content for chunk in chunks])[:5000]

        llm = get_llm(GPT_4O_MINI)
        prompt = ChatPromptTemplate.from_messages([
            ("system", 
             """
             You are a concise summarizer, you will provide a one to two sentence summary capturing the main idea of the provided text.
             You will not add any preamble to the summary or tell me you are giving me a summary, you will simply provide the summary of the provided text.
             """
             ),
            ("user", f"Please summarize the following text in a concise and informative manner: {text}"),
            ("ai", f"Summary: ")
        ])

        promptable_llm = prompt | llm

        output = promptable_llm.invoke({})

        logging.info(f"Summary: {output.dict()}")

        return output.dict()['content'].strip()
    
    @staticmethod
    def get_cleaned_id(id: str) -> str:
        # Convert to lowercase
        id = id.lower()
        
        # Define regex patterns
        patterns = [
            # Remove leading articles and common prepositions
            (r'^(the|a|an|in|on|at|to|for|of)\s+', ''),
            
            # Handle some common irregular verbs
            (r'\b(am|is|are|was|were)\b', 'be'),
            (r'\b(has|had)\b', 'have'),
            (r'\b(does|did)\b', 'do'),
            (r'\b(goes|went)\b', 'go'),
            (r'\b(makes|made)\b', 'make'),
                        
            # Remove any remaining non-alphanumeric characters
            (r'[^a-z0-9\s]', ''),
            
            # Remove extra whitespace
            (r'\s+', ' ')
        ]
        
        # Apply all regex patterns
        for pattern, replacement in patterns:
            id = re.sub(pattern, replacement, id)
        
        return id.strip()
    
    @staticmethod
    def clean_chunks(chunks: List[Document]) -> List[Document]:
        for chunk in chunks:
            chunk.page_content = chunk.page_content.replace("\n", " ")
            chunk.page_content = chunk.page_content.replace("\t", " ")
            chunk.page_content = chunk.page_content.replace("\r", " ")
            chunk.page_content = chunk.page_content.replace("\xa0", " ")
            chunk.page_content = chunk.page_content.replace("’", "'")
            chunk.page_content = chunk.page_content.replace("‘", "'")
            chunk.page_content = chunk.page_content.replace("“", '"')
            chunk.page_content = chunk.page_content.replace("”", '"')
            chunk.page_content = chunk.page_content.replace("…", "...")
            chunk.page_content = chunk.page_content.replace("–", "-")
            chunk.page_content = chunk.page_content.replace("—", "-")
            chunk.page_content = chunk.page_content.replace("´", "'")
            chunk.page_content = chunk.page_content.replace("`", "'")
            chunk.page_content = chunk.page_content.replace("--", "—")
            chunk.page_content = chunk.page_content.replace("---", "—")
            chunk.page_content = chunk.page_content.replace("...", "…")
            chunk.page_content = chunk.page_content.replace("..", "…")
            chunk.page_content = chunk.page_content.replace("''", '"')
            chunk.page_content = chunk.page_content.replace("'", "’")
            chunk.page_content = chunk.page_content.replace('"', '“')
            chunk.page_content = chunk.page_content.replace('…', '...')
            chunk.page_content = chunk.page_content.replace('—', '-')
            chunk.page_content = chunk.page_content.replace('–', '-')
            chunk.page_content = chunk.page_content.replace('´', "'")
            chunk.page_content = chunk.page_content.replace('`', "'")
            chunk.page_content = chunk.page_content.replace('/', ' ')
            chunk.page_content = chunk.page_content.replace('\'', ' ')
        return chunks