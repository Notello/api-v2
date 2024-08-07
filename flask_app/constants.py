import os
from dotenv import load_dotenv
load_dotenv()

NOTE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_note"
QUIZ_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz"
COURSE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_course"
USER_CLASS_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_userclass"
PROFILE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_profile"
QUIZ_QUESTION_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz_question"
TOPIC_SUMMARY_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_topic_summary"
RATE_LIMIT_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_rate_limit"
RATE_LIMIT_VALUES_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_rate_limit_values"

ID = "id"
UUID = "uuid"
COURSEID = "courseId"
USERID = "userId"
NOTEID = "noteId"
SUPAID = "supaId"

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

SUPER_ADMIN_ACCOUNT = "e5e733b0-adc6-43dd-8f24-cd39e2ee924e"

ALGORITHM = "algorithm"
PAGERANK = "pagerank"
LOUVAIN = "louvain"
LEIDEN = "leiden"
COMMUNITY_DETECTION = "community_detection"
NODES = "nodes"
PARAMS = "params"


K8S_VER = '2.07'

proxy_info = {
    'host': 'gate.smartproxy.com',
    'port': 10001,
    'user': 'spcikaf7mg',
    'pass': 'yudB6=zIeGSg19glb7'
}

proxy_url = f"http://{proxy_info['user']}:{proxy_info['pass']}@{proxy_info['host']}:{proxy_info['port']}"

proxy = {
    'http': proxy_url,
    'https': proxy_url
}