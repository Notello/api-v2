from flask import current_app
from runpod import Endpoint
import logging
from .SupabaseService import SupabaseService


class RunpodService:
    @staticmethod
    def transcribe(file_name: str, keywords: str):
        logging.info(f'Transcribing file: {file_name}')

        endpoint: Endpoint = current_app.config['RUNPOD_ENDPOINT']

        try:
            run_request = endpoint.run(
                {
                    "input": {
                        "id": file_name
                    }
                }
            )

            logging.info(f'Runpod job id: {run_request.job_id}')

            output = run_request.output(timeout=600)

            logging.info(f'Runpod job on file: {file_name}')

            runpod_status = run_request.status()

            logging.info(f'Runpod job status: {runpod_status}')

            if runpod_status != 'COMPLETED':
                logging.error(f'Runpod job failed with output: {output}, file: {file_name}, status: {runpod_status}')
                SupabaseService.update_note(file_name, 'contentStatus', 'error')
                return None
            else:
                logging.info(f'Runpod job completed successfully')
                SupabaseService.update_note(file_name, 'contentStatus', 'complete')
                SupabaseService.update_note(file_name, 'rawContent', RunpodService.parse_whisper_output(output))
                return file_name

        except TimeoutError:
            logging.error(f'Runpod job timed out')

        except Exception as e:
            logging.exception(f'Exception Stack trace: {e}')
            return None
        
    @staticmethod
    def parse_whisper_output(output: dict):
        '''
        Going to do more with this later,
        for now just return the text
        '''
        out = ''
        for line in output["data"]:
            out += line["text"] + ' '
        
        return out.strip()