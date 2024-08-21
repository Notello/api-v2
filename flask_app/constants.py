import os
import random
from dotenv import load_dotenv
load_dotenv()

NOTE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_note"
QUIZ_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz"
COURSE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_course"
CHAT_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_chat"
CHAT_MESSAGE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_chat_message"
USER_CLASS_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_userclass"
PROFILE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_profile"
QUIZ_QUESTION_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz_question"
TOPIC_SUMMARY_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_topic_summary"
RATE_LIMIT_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_rate_limit"
RATE_LIMIT_VALUES_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_rate_limit_values"
COLLEGE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_college"
FLASHCARD_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_flashcard"

getGraphKey = lambda id: f"graph:{id}"
getSummaryKey = lambda id: f"summary:{id}"

ID = "id"
UUID = "uuid"
COURSEID = "courseId"
USERID = "userId"
NOTEID = "noteId"
SUPAID = "supaId"
QUIZID = "quizId"

QUIZ = "quiz"
NOTE = "note"
FLASHCARD = "flashcard"
CHAT = "chat"
TOPIC_SUMMARY = "topic_summary"
NOTE_SUMMARY = "note_summary"

FREE = "free"
PREMIUM = "premium"

GPT_35_TURBO_MODEL = "gpt-3.5-turbo-0125"
GPT_4O_MODEL = "gpt-4o"
GPT_4O_MINI = "gpt-4o-mini"
MIXTRAL_MODEL = "mixtral-8x7b-32768"
LLAMA_8_MODEL = "llama3-8b-8192"
LLAMA_8_TOOL_MODEL = "llama3-groq-8b-8192-tool-use-preview"
LLAMA_405_MODEL = "llama-3.1-405b-reasoning"
LLAMA_70B_MODEL = "llama-3.1-70b-versatile"
LLAMA_8B_INSTANT = "llama-3.1-8b-instant"

GROQ_MODELS = [
    LLAMA_8_MODEL,
    LLAMA_8_TOOL_MODEL,
    LLAMA_405_MODEL,
    LLAMA_70B_MODEL,
    LLAMA_8B_INSTANT,
    MIXTRAL_MODEL
]

OPENAI_MODELS = [
    GPT_35_TURBO_MODEL,
    GPT_4O_MODEL,
    GPT_4O_MINI
]
DEFAULT_COMMUNITIES = 3

SUPER_ADMIN_EMAILS = ["aidangollan42@gmail.com", "gollanstrength@gmail.com", "alshaik8@msu.edu", "malshaik.me@gmail.com"]
SUPER_ADMIN_USER_IDS = ['cbd639d0-ff29-46ee-9042-2051d3de71fd', "62ef68a3-7f1d-452c-93d4-136daf5f137b", "67f6b966-5ca3-4710-a80e-2e6c4fdabbf8"]

ALGORITHM = "algorithm"
PAGERANK = "pagerank"
LOUVAIN = "louvain"
LEIDEN = "leiden"
COMMUNITY_DETECTION = "community_detection"
NODES = "nodes"
PARAMS = "params"


K8S_VER = '2.16'

class ProxyRotator:
    def __init__(self):
        self.base_port = 10000
        self.current_port_index = random.randint(0, 9)

    def get_proxy_info(self):
        proxy_port = self.base_port + self.current_port_index

        proxy_info = {
            'host': 'gate.smartproxy.com',
            'port': proxy_port,
            'user': 'spcikaf7mg',
            'pass': 'yudB6=zIeGSg19glb7'
        }

        proxy_url = f"http://{proxy_info['user']}:{proxy_info['pass']}@{proxy_info['host']}:{proxy_info['port']}"

        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def rotate_proxy_port(self):
        self.current_port_index = (self.current_port_index + 1) % 10