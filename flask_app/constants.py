import os
from dotenv import load_dotenv
load_dotenv()

NOTE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_note"
QUIZ_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz"
QUIZ_QUESTION_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz_question"
TOPIC_SUMMARY_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_topic_summary"

ID = "id"
UUID = "uuid"
COURSEID = "courseId"
USERID = "userId"
NOTEID = "noteId"

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

K8S_VER = '1.19'