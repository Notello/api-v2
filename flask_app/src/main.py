import asyncio
import logging
from datetime import datetime
from uuid import uuid4

from flask_app.src.make_relationships import create_relation_between_chunks, merge_relationship_between_chunk_and_entities, update_chunk_embedding
from flask_app.src.shared.common_fn import clean_nodes
from flask_app.src.openAI_llm import get_graph_from_OpenAI
from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.NodeUpdateService import NodeUpdateService
from flask_app.services.SupaGraphService import SupaGraphService
from flask_app.services.GraphUpdateService import GraphUpdateService
from flask_app.constants import NOTEID

async def processing_source(
      fileName: str, 
      chunks, 
      userId,
      courseId,
      noteId,
      summary
      ):
        
    logging.info("Break down file into chunks")

    await asyncio.to_thread(SupabaseService.update_note, noteId, 'graphStatus', '1')
    
    logging.info('Update the status as Processing')

    tasks = []
    nodes_data = []

    logging.info(f"Total chunks: {len(chunks)}")

    try:
        for i, chunk in enumerate(chunks):
            task = asyncio.create_task(
                process_chunks(
                    chunk=chunk,
                    noteId=noteId,
                    courseId=courseId,
                    userId=userId,
                    startI=i,
                    document_name=fileName,
                    summary=summary
                )
            )
            tasks.append(task)

        for i, completed_task in enumerate(asyncio.as_completed(tasks)):
            logging.info(f"Task {i} is done")
            result = await completed_task
            nodes_data.extend(result if result is not None else [])
            await asyncio.to_thread(SupabaseService.update_note, noteId, 'graphStatus', str(uuid4()))
    except Exception as e:
        logging.exception(f"Error in processing chunks: {e}")
        raise e
    
    await asyncio.to_thread(SupaGraphService.merge_similar_nodes, courseId)
    logging.info(f"Setting mergeStatus to complete for course {courseId}")

    await asyncio.to_thread(SupaGraphService.update_embeddings, courseId)
    logging.info(f"Setting comStatus to complete for course {courseId}")

    await asyncio.to_thread(GraphUpdateService.update_graph_positions, courseId)

    await asyncio.to_thread(SupabaseService.update_note, noteId=noteId, key='graphStatus', value='complete')
    
    logging.info('Updated the nodeCount and relCount properties in Document node')
    logging.info(f'File: {fileName} extraction has been completed')

async def process_chunks(
    chunk, 
    noteId,
    courseId,
    userId,
    startI,
    document_name,
    summary
):
    try:
        logging.info(f"Starting process_chunks for chunk {startI}")

        chunk_id = await asyncio.to_thread(
            SupaGraphService.insert_chunk,
            noteId=noteId,
            courseId=courseId,
            chunk=chunk,
            document_name=document_name
        )

        logging.info("Get graph document list from models")

        graph_document = await asyncio.to_thread(
            get_graph_from_OpenAI,
            chunk=chunk,
            summary=summary,
        )

        graph_doc = clean_nodes(doc=graph_document, courseId=courseId, noteId=noteId, userId=userId)

        nodes_data = await asyncio.to_thread(
            SupaGraphService.insert_topics,
            graph_document=graph_doc,
            noteId=noteId,
            courseId=courseId
        )

        await asyncio.to_thread(
            SupaGraphService.connect_topics,
            nodes=nodes_data,
            chunk_id=chunk_id,
            noteId=noteId,
        )

        return nodes_data
    except Exception as e:
        logging.exception(f"Error in process_chunks: {e}")

def processing_source_sync(*args, **kwargs):
    return asyncio.run(processing_source(*args, **kwargs))