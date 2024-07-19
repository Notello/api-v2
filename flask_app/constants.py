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
LLAMA_8_TOOL_MODEL = "llama3-groq-8b-8192-tool-use-preview"
DEFAULT_COMMUNITIES = 3