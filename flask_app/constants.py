import os
from dotenv import load_dotenv
load_dotenv()

NOTE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_note"
QUIZ_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz"
QUIZ_QUESTION_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_quiz_question"

GPT_35_TURBO_MODEL = "gpt-3.5-turbo-0125"
MIXTRAL_MODEL = "mixtral-8x7b-32768"
APPROVED_MODELS = [GPT_35_TURBO_MODEL, MIXTRAL_MODEL]
DEFAULT_COMMUNITIES = 3