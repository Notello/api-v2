import runpod
import os
from runpod import Endpoint
import logging

from .SupabaseService import SupabaseService
from flask_app.constants import ALGORITHM, COMMUNITY_DETECTION, NODES, PAGERANK, PARAMS

class RunpodService:
    @staticmethod
    def transcribe(fileName: str) -> str | None:
        logging.info(f'Transcribing file: {fileName}')

        endpoint: Endpoint = runpod.Endpoint(os.getenv("RUNPOD_WHISPER_ENDPOINT_ID"))

        try:
            run_request = endpoint.run(
                {
                    "input": {
                        "id": fileName
                    }
                }
            )

            logging.info(f'Runpod job id: {run_request.job_id}')

            output = run_request.output(timeout=600)

            logging.info(f'Runpod job on file: {fileName}')

            runpod_status = run_request.status()

            logging.info(f'Runpod job status: {runpod_status}')

            if runpod_status != 'COMPLETED':
                logging.error(f'Runpod job failed with output: {output}, file: {fileName}, status: {runpod_status}')
                SupabaseService.update_note(fileName, 'contentStatus', 'error')
                return None
            else:
                logging.info(f'Runpod job completed successfully')

                outputFormatted = RunpodService.parse_whisper_output(output)
                SupabaseService.update_note(fileName, 'contentStatus', 'complete')
                SupabaseService.update_note(fileName, 'rawContent', outputFormatted)
                return output

        except TimeoutError:
            logging.error(f'Runpod job timed out')
            return None

        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
            return None
        
    @staticmethod
    def parse_whisper_output(output: dict):
        '''
        Going to do more with this later,
        for now just return the text
        '''
        logging.info(f'Parsing output: {output}')
        out = ''
        for line in output["data"]:
            out += line["text"] + ' '
        
        return out.strip()
    
    @staticmethod
    def run_pagerank(graph):
        logging.info(f'Running Pagerank on graph: {graph}')
    
    @staticmethod
    def run_community_detection(graph):
        logging.info(f'Running Community Detection on graph')


    @staticmethod
    def run_gds(graph, algorithm_type, algorithm):
        
        if algorithm_type != PAGERANK and algorithm_type != COMMUNITY_DETECTION:
            logging.error(f'Invalid algorithm: {algorithm}')
            return None
        
        logging.info(f'Running {algorithm_type} {algorithm} on graph')

        endpoint: Endpoint = runpod.Endpoint(os.getenv("RUNPOD_GDS_ENDPOINT_ID"))

        try:
            run_request = endpoint.run(
                {
                    "input": {
                        NODES: graph,
                        ALGORITHM: algorithm_type,
                        PARAMS: {
                            ALGORITHM: algorithm
                        }
                    }
                }
            )

            logging.info(f'Runpod job id: {run_request.job_id}')

            output = run_request.output(timeout=600)

            logging.info(f'Pagerank fin')

            runpod_status = run_request.status()

            logging.info(f'Runpod job status: {runpod_status}')

            if runpod_status != 'COMPLETED':
                logging.error(f'Runpod job failed with output: {output}, algorithm: {algorithm}, algorithm_type: {algorithm_type}, status: {runpod_status}')
                return None
            else:
                logging.info(f'Runpod job completed successfully')
                return output.get('data')
        
        except TimeoutError:
            logging.error(f'Runpod job timed out')
            return None

        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
            return None