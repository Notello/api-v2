from neo4j import GraphDatabase, Record, Result
import os
from retry import retry
import logging
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError
import time
from threading import Lock

class Neo4jConnection:
    _driver = None
    _lock = Lock()

    @classmethod
    def initialize(cls):
        with cls._lock:
            if cls._driver is None:
                uri = os.getenv('NEO4J_URI')
                user = os.getenv('NEO4J_USERNAME')
                password = os.getenv('NEO4J_PASSWORD')
                cls._driver = GraphDatabase.driver(
                    uri,
                    auth=(user, password),
                    max_connection_pool_size=10000
                )
        logging.info("Neo4j connection initialized")

    @classmethod
    def get_session(cls):
        if cls._driver is None:
            cls.initialize()
        return cls._driver.session(database=os.getenv('NEO4J_DATABASE'))

    @classmethod
    def close(cls):
        with cls._lock:
            if cls._driver:
                cls._driver.close()
                cls._driver = None
        logging.info("Neo4j connection closed")

    @classmethod
    @retry(exceptions=(ServiceUnavailable, SessionExpired, TransientError), tries=5, delay=1, backoff=2, jitter=(1, 3))
    def run_query(cls, query, params=None):
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                with cls.get_session() as session:
                    result: Result = session.run(query, params)
                    return result.data()
            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            except Exception as e:
                logging.error(f"Query execution failed: {str(e)}")
                raise