import logging
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from langchain_experimental.graph_transformers import LLMGraphTransformer

from flask_app.src.shared.common_fn import get_combined_chunks, get_llm

logging.basicConfig(format='%(asctime)s - %(message)s',level='INFO')

from flask import current_app

def get_graph_from_OpenAI(chunkId_chunkDoc_list, allowedNodes, allowedRelationship):
    futures=[]
    graph_document_list=[]

    combined_chunk_document_list = get_combined_chunks(chunkId_chunkDoc_list)

    llm = get_llm(current_app.config['MODEL'])
    llm_transformer = LLMGraphTransformer(
        llm=llm, 
        allowed_nodes=['Concept'], 
        allowed_relationships=allowedRelationship,
        node_properties=["description"]
        )
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        for chunk in combined_chunk_document_list:
            futures.append(
                executor.submit(
                    llm_transformer.convert_to_graph_documents,
                    [chunk]
                ))
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            graph_document = future.result()
            graph_document_list.append(graph_document[0])   

    return graph_document_list        
        
    
    
