from datetime import datetime

class sourceNode:
    fileName:str=None
    file_size:int=None
    file_type:str=None
    file_source:str=None
    courseId:str=None
    userId:str=None
    noteId:str=None
    status:str=None
    url:str=None
    gcsBucket:str=None
    gcsBucketFolder:str=None
    gcsProjectId:str=None
    awsAccessKeyId:str=None
    node_count:int=None
    relationship_count:str=None
    model:str=None
    created_at:datetime=None
    updated_at:datetime=None
    processing_time:float=None
    error_message:str=None
    total_pages:int=None
    total_chunks:int=None
    language:str=None
    is_cancelled:bool=None
    processed_chunk:int=None
