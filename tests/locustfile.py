import os
import requests
from locust import HttpUser, task, between, events
from itertools import cycle

# Global variables
EMAIL = 'gollanstrength@gmail.com'
PASSWORD = 'password123'
LOGIN_URL = f"http://localhost:5000/auth/login/{EMAIL}/{PASSWORD}"
SHARED_TOKEN = None

def login():
    global SHARED_TOKEN
    response = requests.get(LOGIN_URL)
    if response.status_code == 200:
        SHARED_TOKEN = response.json()
        print(f"Login successful. Token: {SHARED_TOKEN}")
    else:
        print(f"Login failed: HTTP {response.status_code}")
        print(f"Response content: {response.text}")
        exit(1)

# Call login at the top of the script
login()

class PDFUploadUser(HttpUser):
    wait_time = between(0, .1)  # Minimize wait time between tasks
    host = "http://localhost:5000"
    pdf_files = []
    file_cycle = None

    @classmethod
    def create_file_cycle(cls):
        folder_path = 'bible'
        cls.pdf_files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]
        cls.pdf_files.sort()
        cls.file_cycle = cycle(cls.pdf_files)

    def on_start(self):
        if not PDFUploadUser.file_cycle:
            PDFUploadUser.create_file_cycle()
        self.current_file = next(PDFUploadUser.file_cycle)

    @task
    def upload_pdf(self):
        if not self.current_file:
            print("No PDF file available for upload.")
            return

        file_path = os.path.join('bible', self.current_file)

        user_id = '2d9abff2-1d93-482e-9e30-eede771f30ce'
        course_id = '37095609-eb18-4ccc-b104-43df97586782'
        ingest_type = 'create'

        with open(file_path, 'rb') as file:
            files = {'file': (self.current_file, file, 'application/pdf')}
            data = {
                'userId': user_id,
                'courseId': course_id,
                'ingestType': ingest_type
            }
            headers = {'Authorization': f'Bearer {SHARED_TOKEN}'}
            response = self.client.post("/note/create-text-file-note", 
                                        files=files, 
                                        data=data, 
                                        headers=headers)
            
            if response.status_code < 400:
                print(f"Successfully uploaded {self.current_file}")
            else:
                print(f"Error uploading {self.current_file}: HTTP {response.status_code}")
                print(f"Response content: {response.text}")

        # Exit after one action
        self.environment.runner.quit()

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("All users are spawned, starting test...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("Test finished")