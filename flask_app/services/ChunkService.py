from typing import Dict, List

import tiktoken
from langchain.docstore.document import Document
from pytube import YouTube

class ChunkService:
    @staticmethod
    def count_tokens(text):
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))

    @staticmethod
    def get_timestamp_chunks(
        transcript: List[Dict[str, str]],
        max_tokens=500,
        overlap=100,
    ):
        chunks = []
        current_chunk = {"text": "", "start": None, "end": None, "tokens": 0}
        
        for entry in transcript:
            text = entry['text']
            start = entry['start']
            
            tokens = ChunkService.count_tokens(text)
            
            if current_chunk["tokens"] + tokens > max_tokens:
                # Finish current chunk
                chunks.append(Document(
                    page_content=current_chunk["text"].strip(),
                    metadata={
                        "start": current_chunk["start"],
                    }
                ))
                
                # Start new chunk with overlap
                overlap_text = " ".join(current_chunk["text"].split()[-overlap:])
                current_chunk = {
                    "text": overlap_text + " " + text,
                    "start": start,
                    "tokens": ChunkService.count_tokens(overlap_text) + tokens
                }
            else:
                # Add to current chunk
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
    ):
        pass