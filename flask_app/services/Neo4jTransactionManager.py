import os
import time
import random
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError
import logging
from functools import wraps
from flask import current_app

class Neo4jTransactionManager:
    def __init__(self, uri=os.getenv('NEO4J_URI'), user=os.getenv('NEO4J_USERNAME'), password=os.getenv('NEO4J_PASSWORD')):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def execute_transaction(self, work_func, *args, **kwargs):
        max_retries = 5
        base_retry_time = 1
        max_retry_time = 16

        for retry_count in range(max_retries):
            try:
                with self.driver.session() as session:
                    result = session.execute_write(self._run_transaction, work_func, *args, **kwargs)
                return result
            except (ServiceUnavailable, SessionExpired) as e:
                logging.warning(f"Transaction failed due to service unavailable (attempt {retry_count + 1}): {str(e)}")
                if retry_count == max_retries - 1:
                    raise
            except TransientError as e:
                if "deadlock" in str(e).lower():
                    retry_time = min(base_retry_time * (2 ** retry_count) + random.uniform(0, 1), max_retry_time)
                    logging.warning(f"Deadlock detected (attempt {retry_count + 1}). Retrying in {retry_time:.2f} seconds.")
                    time.sleep(retry_time)
                    if retry_count == max_retries - 1:
                        raise
                else:
                    raise
        
        raise Exception("Transaction failed after maximum retries")

    @staticmethod
    def _run_transaction(tx, work_func, *args, **kwargs):
        return work_func(tx, *args, **kwargs)

def transactional(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        tx_manager = Neo4jTransactionManager()
        try:
            result = tx_manager.execute_transaction(func, *args, **kwargs)
            return result
        finally:
            tx_manager.close()
    return wrapper