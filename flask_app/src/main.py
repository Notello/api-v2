import sys
from pytube import YouTube
from datetime import datetime
import logging
import re
from flask_app.src.document_sources.youtube import get_youtube_transcript
from flask_app.src.entities.source_node import sourceNode
from flask_app.src.graphDB_dataAccess import graphDBdataAccess
from flask_app.src.shared.common_fn import check_url_source

from flask import current_app

def create_source_node_graph_url_youtube(source_url):
    
    youtube_url, language = check_url_source(yt_url=source_url)
    success_count=0
    failed_count=0
    lst_file_name = []
    obj_source_node = sourceNode()
    obj_source_node.file_type = 'text'
    obj_source_node.file_source = 'youtube'
    obj_source_node.model = 'gpt-4o'
    obj_source_node.url = youtube_url
    obj_source_node.created_at = datetime.now()
    match = re.search(r'(?:v=)([0-9A-Za-z_-]{11})\s*',obj_source_node.url)
    logging.info(f"match value{match}")

    obj_source_node.file_name = YouTube(obj_source_node.url).title
    transcript= get_youtube_transcript(match.group(1))

    if transcript==None or len(transcript)==0:
      message = f"Youtube transcript is not available for : {obj_source_node.file_name}"
      raise Exception(message)
    else:  
      obj_source_node.file_size = sys.getsizeof(transcript)
    
    graphDb_data_Access = graphDBdataAccess(current_app.config['NEO4J_GRAPH'])
    graphDb_data_Access.create_source_node(obj_source_node)
    lst_file_name.append({'fileName':obj_source_node.file_name,'fileSize':obj_source_node.file_size,'url':obj_source_node.url,'status':'Success'})
    success_count+=1
    return lst_file_name,success_count,failed_count
