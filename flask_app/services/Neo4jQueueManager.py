import os
import time
import random
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError
import logging
from functools import wraps
from queue import Queue
from threading import Thread, Lock
from typing import Callable, Dict, Any
from flask_app.constants import COURSEID, NOTEID

class Neo4jQueueManager:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Neo4jQueueManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
        )
        self.queue = Queue()
        self.course_tasks: Dict[str, Dict[str, Any]] = {}
        self.worker_thread = Thread(target=self._worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def close(self):
        self.queue.join()
        self.driver.close()

    def _worker(self):
        while True:
            task = self.queue.get()
            if task is None:
                break
            work_func, args, kwargs, result_queue, task_type, course_id, note_id, id_type = task
            try:
                if course_id and self._should_skip_processing(course_id, note_id, task_type):
                    logging.info(f"Skipping task: {task_type} for course {course_id}")
                    result_queue.put(('skipped', None))
                else:
                    logging.info(f"Processing task: {task_type} for course {course_id}")
                    kwargs['note_id'] = note_id
                    kwargs['id_type'] = id_type
                    result = self._execute_transaction(work_func, *args, **kwargs)
                    result_queue.put(('success', result))
            except Exception as e:
                result_queue.put(('error', str(e)))
            finally:
                self.queue.task_done()
                if task_type in ['community', 'pagerank', 'merge'] and course_id:
                    with self._lock:
                        if course_id in self.course_tasks:
                            self.course_tasks[course_id].pop(task_type, None)
                            if not self.course_tasks[course_id]:
                                del self.course_tasks[course_id]


    def _should_skip_processing(self, course_id: str, note_id: str, task_type: str) -> bool:
        status_field = {
            'merge': 'mergeStatus',
            'community': 'comStatus',
            'pagerank': 'pagerankStatus'
        }.get(task_type, 'status')

        logging.info(f"status_field: {status_field}")

        query = f"""
        MATCH (d:Document)
        WHERE d.courseId = $courseId AND d.noteId <> $noteId
        WITH d.{status_field} AS status
        WHERE status <> 'complete'
        RETURN count(status) AS count
        ORDER BY count DESC
        """

        logging.info(f"query: {query}")

        with self.driver.session() as session:
            result = session.run(query, courseId=course_id, noteId=note_id)
            out = result.single()['count']
            logging.info(f"out: {out}")
            logging.info("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            return out != 0

    def _execute_transaction(self, work_func, *args, **kwargs):
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

    def enqueue_transaction(self, work_func: Callable, *args, task_type: str = None, course_id: str = None, note_id: str = None, id_type: str = None, **kwargs):
        if note_id is None:
            raise ValueError("noteId is mandatory for all operations")

        result_queue = Queue()

        # If it's a noteId operation, process it immediately
        if id_type == NOTEID:
            try:
                result = self._execute_transaction(work_func, *args, id_type=id_type, note_id=note_id, **kwargs)
                return result
            except Exception as e:
                raise Exception(f"Error processing noteId transaction: {str(e)}")

        # For other operations, use the queue
        with self._lock:
            if task_type in ['community', 'pagerank', 'merge'] and course_id:
                if course_id not in self.course_tasks:
                    self.course_tasks[course_id] = {}
                
                if task_type in self.course_tasks[course_id]:
                    old_task = self.course_tasks[course_id][task_type]
                    old_task['result_queue'].put(('cancelled', None))
                
                self.course_tasks[course_id][task_type] = {
                    'work_func': work_func,
                    'args': args,
                    'kwargs': kwargs,
                    'result_queue': result_queue
                }
            
            self.queue.put((work_func, args, kwargs, result_queue, task_type, course_id, note_id, id_type))
        
        status, result = result_queue.get()
        if status == 'error':
            raise Exception(result)
        elif status == 'cancelled':
            logging.info(f"Task cancelled: {work_func.__name__} for course {course_id}")
            return None
        elif status == 'skipped':
            logging.info(f"Task skipped: {work_func.__name__} for course {course_id}")
            return None
        return result

def queued_transaction(task_type: str = None):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            queue_manager = Neo4jQueueManager()
            
            id_type = kwargs.get('id_type')
            target_id = kwargs.get('target_id')
            note_id = kwargs.get('note_id')
            
            if id_type is None or target_id is None or note_id is None:
                start_index = 1 if len(args) > 0 and str(args[0]).startswith("<neo4j.work.session.") else 0
                if len(args) >= start_index + 3:
                    id_type = args[start_index]
                    target_id = args[start_index + 1]
                    note_id = args[start_index + 2]
                else:
                    raise ValueError("Missing required arguments: id_type, target_id, and note_id")
            
            course_id = target_id if id_type == COURSEID else None

            kwargs.pop('id_type', None)
            kwargs.pop('target_id', None)
            kwargs.pop('note_id', None)
            
            return queue_manager.enqueue_transaction(func, *args, task_type=task_type, course_id=course_id, id_type=id_type, target_id=target_id, note_id=note_id, **kwargs)
        return wrapper
    return decorator