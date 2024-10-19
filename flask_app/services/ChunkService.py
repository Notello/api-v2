import logging
import re
from typing import Dict, List

import tiktoken
from langchain.docstore.document import Document
from pytube import YouTube
from flask_app.services.HelperService import HelperService

class ChunkService:
    @staticmethod
    def count_tokens(text):
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))

    @staticmethod
    def clean_text(text):
        # Remove f-string brackets
        text = re.sub(r'{[^}]*}', '', text)
        
        # Remove single-line comments
        text = re.sub(r'//.*', '', text)
        
        # Remove multi-line comments
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        
        # Remove other potentially problematic characters
        text = re.sub(r'[<>{}]', '', text)
        
        # Replace multiple spaces with a single space
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    @staticmethod
    def get_timestamp_chunks(
        transcript: List[Dict[str, str]],
        max_tokens=5000,
        overlap=500,
    ):
        chunks = []
        current_chunk = {"text": "", "start": None, "tokens": 0}
        
        full_transcript = " ".join(ChunkService.clean_text(entry['text']) for entry in transcript)
        total_tokens = ChunkService.count_tokens(full_transcript)
        max_tokens_calc = max(min(total_tokens // 4, 5000), 500)
        overlap_calc = max(min(total_tokens // 10, 500), 100)
        
        for entry in transcript:
            text = ChunkService.clean_text(entry['text'])
            start = entry['start']
            
            tokens = ChunkService.count_tokens(text)
            
            if current_chunk["tokens"] + tokens > max_tokens_calc:
                chunks.append(Document(
                    page_content=current_chunk["text"].strip(),
                    metadata={
                        "start": current_chunk["start"],
                    }
                ))
                
                overlap_text = " ".join(current_chunk["text"].split()[-overlap_calc:])
                current_chunk = {
                    "text": overlap_text + " " + text,
                    "start": start,
                    "tokens": ChunkService.count_tokens(overlap_text) + tokens
                }
            else:
                if current_chunk["start"] is None:
                    current_chunk["start"] = start
                current_chunk["text"] += " " + text
                current_chunk["tokens"] += tokens
        
        if current_chunk["text"]:
            chunks.append(Document(
                page_content=current_chunk["text"].strip(),
                metadata={
                    "start": current_chunk["start"],
                }
            ))
        
        return chunks

    @staticmethod
    def get_text_chunks(
        text: str,
        max_tokens=5000,
        overlap=500,
    ) -> List[Document]:
        chunks = []
        current_chunk = {"text": "", "start": 0, "tokens": 0}
        words = ChunkService.clean_text(text).split()

        max_tokens_calc = max(min(len(words) // 4, 5000), 500)
        overlap_calc = max(min(len(words) // 10, 500), 100)
        
        for i, word in enumerate(words):
            tokens = ChunkService.count_tokens(word)
            
            if current_chunk["tokens"] + tokens > max_tokens_calc:
                chunks.append(Document(
                    page_content=current_chunk["text"].strip(),
                    metadata={
                        "start": current_chunk["start"],
                    }
                ))
                
                current_chunk = {"text": "", "start": i, "tokens": 0}
            else:
                current_chunk["text"] += " " + word
                current_chunk["tokens"] += tokens
        
        if current_chunk["text"]:
            chunks.append(Document(
                page_content=current_chunk["text"].strip(),
                metadata={
                    "start": current_chunk["start"],
                }
            ))

        return chunks