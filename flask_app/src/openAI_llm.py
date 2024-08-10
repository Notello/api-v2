import logging
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from langchain_experimental.graph_transformers import LLMGraphTransformer
from flask_app.src.CustomGraphBuilder import LLMGraphTransformer as CustomGraphTransformer
from langchain.docstore.document import Document

from flask_app.src.shared.common_fn import clean_nodes, get_combined_chunks, get_llm
from flask_app.constants import GPT_35_TURBO_MODEL, GPT_4O_MINI, LLAMA_8B_INSTANT

logging.basicConfig(format='%(asctime)s - %(message)s',level='INFO')


def get_graph_from_OpenAI(chunk_with_id):
    try:
        llm = get_llm(GPT_4O_MINI)
        llm_transformer = CustomGraphTransformer(
            llm=llm, 
            allowed_nodes=['Concept'], 
            )
        
        document = Document(page_content=chunk_with_id.get('pg_content'))
        
        graph_document = llm_transformer.convert_to_graph_documents([document])
        
        graph_docs_final = clean_nodes(graph_document)

        return graph_docs_final  
    except Exception as e:
        logging.exception(f"Error in get_graph_from_OpenAI: {e}")
        raise e