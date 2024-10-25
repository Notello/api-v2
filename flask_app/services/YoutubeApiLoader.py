import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
from typing import List, Dict, Tuple
from youtube_transcript_api import YouTubeTranscriptApi
import logging

from dotenv import load_dotenv
load_dotenv()

class YouTubeTranscriptFetcher:
    def __init__(self):
        """
        Initialize with service account credentials
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        credentials_path = os.path.join(project_root, 'notello-d35a3e1d01e2.json')

        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
        )
        self.youtube = build('youtube', 'v3', credentials=self.credentials)

    def extract_video_id(self, youtube_url: str) -> str:
        """Extract video ID from YouTube URL"""
        if 'youtu.be' in youtube_url:
            return youtube_url.split('/')[-1]
        elif 'youtube.com' in youtube_url:
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(youtube_url)
            return parse_qs(parsed_url.query)['v'][0]
        return youtube_url

    def get_video_metadata(self, youtube_url: str) -> Dict:
        """
        Fetch video metadata including title, description, etc.
        Returns a dictionary containing video information
        """
        video_id = self.extract_video_id(youtube_url)
        
        try:
            # Call the videos().list method to retrieve video details
            video_response = self.youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            ).execute()

            if not video_response.get('items'):
                raise ValueError(f"No video found for ID: {video_id}")

            video_data = video_response['items'][0]['snippet']
            return {
                'title': video_data.get('title'),
                'description': video_data.get('description'),
                'published_at': video_data.get('publishedAt'),
                'channel_title': video_data.get('channelTitle'),
                'tags': video_data.get('tags', [])
            }
        except Exception as e:
            logging.error(f"Failed to fetch video metadata: {e}")
            raise ValueError(f"Could not fetch video metadata: {str(e)}")

    def get_video_title(self, youtube_url: str) -> str:
        """
        Fetch just the title of the YouTube video
        Returns the title as a string
        """
        try:
            metadata = self.get_video_metadata(youtube_url)
            return metadata['title']
        except Exception as e:
            logging.error(f"Failed to fetch video title: {e}")
            raise ValueError(f"Could not fetch video title: {str(e)}")

    def get_transcript_and_title(self, youtube_url: str) -> Tuple[str, str]:
        """
        Fetch both transcript and title in one call
        Returns a tuple of (transcript, title)
        """
        title = self.get_video_title(youtube_url)
        transcript = self.get_transcript(youtube_url)
        return transcript, title

    def get_transcript(self, youtube_url: str) -> str:
        """
        Fetch transcript for a YouTube video
        Returns the transcript as a string
        """
        video_id = self.extract_video_id(youtube_url)
        
        try:
            # First try using youtube_transcript_api for easier access
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            return self._process_transcript_list(transcript_list)
        except Exception as e:
            logging.warning(f"Failed to get transcript via YouTubeTranscriptApi: {e}")
            
            # Fallback to official API
            try:
                captions_response = self.youtube.captions().list(
                    part='snippet',
                    videoId=video_id
                ).execute()

                caption_id = None
                for item in captions_response.get('items', []):
                    if item['snippet']['language'] == 'en':
                        caption_id = item['id']
                        if item['snippet']['trackKind'] != 'ASR':
                            break

                if not caption_id:
                    raise ValueError("No English captions found for this video")

                transcript = self.youtube.captions().download(
                    id=caption_id,
                    tfmt='srt'
                ).execute()

                return self._process_srt_transcript(transcript)
            
            except Exception as e:
                logging.error(f"Failed to get transcript via official API: {e}")
                raise ValueError(f"Could not fetch transcript: {str(e)}")

    def _process_transcript_list(self, transcript_list: List[Dict]) -> str:
        """Process transcript from youtube_transcript_api format"""
        return ' '.join(item['text'] for item in transcript_list)

    def _process_srt_transcript(self, raw_transcript: str) -> str:
        """Process transcript from SRT format"""
        lines = raw_transcript.splitlines()
        processed_lines = []
        
        for line in lines:
            if (not line.strip() or 
                line.strip().isdigit() or 
                '-->' in line):
                continue
            processed_lines.append(line.strip())
        
        return ' '.join(processed_lines)