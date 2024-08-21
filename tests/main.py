import os
import asyncio
import aiohttp
from aiofiles import open as aopen
from aiohttp import ClientSession, TCPConnector

async def login(session, base_url, email, password):
    login_url = f"{base_url}/auth/login/{email}/{password}"
    async with session.get(login_url) as response:
        if response.status == 200:
            data = await response.json()
            return data
        else:
            print(f"Login failed: HTTP {response.status}")
            print(f"Response content: {await response.text()}")
            return None

async def upload_pdf(session, api_url, file_path, course_id, ingest_type, headers):
    async with aopen(file_path, 'rb') as file:
        pdf_file = os.path.basename(file_path)
        form_data = aiohttp.FormData()
        form_data.add_field('file', await file.read(), filename=pdf_file, content_type='application/pdf')
        form_data.add_field('courseId', course_id)
        form_data.add_field('ingestType', ingest_type)

        try:
            async with session.post(api_url, data=form_data, headers=headers) as response:
                await response.text()
                if response.status < 400:
                    print(f"Successfully uploaded {pdf_file}")
                    return True
                else:
                    print(f"Error uploading {pdf_file}: HTTP {response.status}")
                    print(f"Response content: {await response.text()}")
                    return False
        except Exception as e:
            print(f"Error uploading {pdf_file}: {str(e)}")
            return False

async def simulate_concurrent_uploads(folder_path, base_url, course_id, ingest_type, email, password, num_users=500):
    if not os.path.exists(folder_path):
        print(f"Error: Folder '{folder_path}' does not exist.")
        return

    pdf_files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]

    if not pdf_files:
        print(f"No PDF files found in '{folder_path}'.")
        return

    pdf_files.sort()

    connector = TCPConnector(limit=0)  # Remove limit to allow maximum concurrent connections
    async with ClientSession(connector=connector) as session:
        bearer_token = await login(session, base_url, email, password)
        if not bearer_token:
            print("Login failed. Unable to proceed with uploads.")
            return

        headers = {
            'Authorization': f'Bearer {bearer_token}'
        }

        api_url = f"{base_url}/note/create-text-file-note"
        
        # Create a list of tasks for concurrent execution
        tasks = []
        for _ in range(num_users):
            # If there are fewer PDF files than users, cycle through the files
            file_index = _ % len(pdf_files)
            file_path = os.path.join(folder_path, pdf_files[file_index])
            task = upload_pdf(session, api_url, file_path, course_id, ingest_type, headers)
            tasks.append(task)

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks)

    successful_uploads = sum(results)
    print(f"Simulation complete. Successfully uploaded {successful_uploads} out of {num_users} requests.")

# Usage
base_url = 'https://api.notello.dev'  # Adjust this to your actual base URL
local_url = 'http://localhost:5000'
folder_path = 'bible'
course_id = '62ef68a3-7f1d-452c-93d4-136daf5f137b'
ingest_type = 'create'
email = 'gollanstrength@gmail.com'  # Replace with actual email
password = 'password123'  # Replace with actual password

asyncio.run(simulate_concurrent_uploads(folder_path, local_url, course_id, ingest_type, email, password, num_users=1))