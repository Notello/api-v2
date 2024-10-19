import logging
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from langchain_experimental.graph_transformers import LLMGraphTransformer
from flask_app.src.CustomGraphBuilder import LLMGraphTransformer as CustomGraphTransformer
from flask_app.src.CustomKGBuilder import CustomKGBuilder
from langchain.docstore.document import Document

from flask_app.src.shared.common_fn import clean_nodes

logging.basicConfig(format='%(asctime)s - %(message)s',level='INFO')


def get_graph_from_OpenAI(
        chunk: Document, 
        summary,
        ):
    try:        
        return CustomKGBuilder.create_knowledge_graph(
            text=chunk.page_content,
            summary=summary
            )
    except Exception as e:
        logging.exception(f"Error in get_graph_from_OpenAI: {e}")
        raise e