import os
from dotenv import load_dotenv
load_dotenv()

NOTE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_note"
QUIZ_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz"
QUIZ_QUESTION_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz_question"
SUMMARY_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_note_summary"

GPT_35_TURBO_MODEL = "gpt-3.5-turbo-0125"
GPT_4O_MODEL = "gpt-4o"
GPT_4O_MINI = "gpt-4o-mini"
MIXTRAL_MODEL = "mixtral-8x7b-32768"
LLAMA_8_MODEL = "llama3-8b-8192"
APPROVED_MODELS = [GPT_35_TURBO_MODEL, MIXTRAL_MODEL, LLAMA_8_MODEL, GPT_4O_MODEL, GPT_4O_MINI]
DEFAULT_COMMUNITIES = 3