import os
from dotenv import load_dotenv
load_dotenv()

CHAT_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_chat"
COURSE_TABLE_NAME = f"{os.getenv('ENV_TYPE')}_webapp-v2_course"
COLLEGE_ID = "24d06b26-97b2-4c07-a6e2-6229e930f55c"