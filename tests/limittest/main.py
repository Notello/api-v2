import os
import random
import asyncio
import aiohttp
from aiofiles import open as aopen
from aiohttp import ClientSession, TCPConnector
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

local = False
base_url = 'https://api.notello.dev'
local_url = 'http://localhost:5000'
folder_path = 'bible'
course_id = '62ef68a3-7f1d-452c-93d4-136daf5f137b'
local_course_id = '37095609-eb18-4ccc-b104-43df97586782'
ingest_type = 'create'
local_email = 'aidangollan42@gmail.com'
local_password = 'password'
email = 'gollanstrength@gmail.com'
password = 'password123'
num_users = 50
duration_minutes = 30


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

        start_time = datetime.now()
        try:
            async with session.post(api_url, data=form_data, headers=headers) as response:
                await response.text()
                end_time = datetime.now()
                response_time = (end_time - start_time).total_seconds()
                if response.status < 400:
                    print(f"Successfully uploaded {pdf_file}")
                    print(f"Response time: {response_time:.2f} seconds")
                    return True, response_time
                else:
                    print(f"Error uploading {pdf_file}: HTTP {response.status}")
                    print(f"Response content: {await response.text()}")
                    return False, response_time
        except Exception as e:
            print(f"Error uploading {pdf_file}: {str(e)}")
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            return False, response_time

async def simulate_concurrent_uploads(folder_path, base_url, course_id, ingest_type, email, password, num_users=500):
    print(f"testing")
    try:
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

            print(api_url)
            
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

            print(f"results: {results}")

        time = sum(time for _, time in results)
        successful_uploads = sum(success for success, _ in results)
        print(f"Test complete. Successfully uploaded {successful_uploads} out of {len(tasks)} requests over {duration_minutes} minutes.")
        print(f"Average response time: {time / len(tasks):.2f} seconds")
    except Exception as e:
        print(f"Error: {str(e)}")

async def timed_concurrent_uploads(folder_path, base_url, course_id, ingest_type, email, password, num_users=500, duration_minutes=30):
    print("Starting timed concurrent uploads test")
    try:
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

            print(f"API URL: {api_url}")
            
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=duration_minutes)

            tasks = []
            for i in range(num_users):
                # Calculate a random delay within the remaining time
                max_delay = (end_time - datetime.now()).total_seconds()
                if max_delay <= 0:
                    print(f"Time limit reached. Stopping after {i} users.")
                    break
                delay = random.uniform(0, max_delay)

                # If there are fewer PDF files than users, cycle through the files
                file_index = i % len(pdf_files)
                file_path = os.path.join(folder_path, pdf_files[file_index])
                
                task = asyncio.create_task(delayed_upload(session, api_url, file_path, course_id, ingest_type, headers, delay))
                tasks.append(task)

            results = await asyncio.gather(*tasks)

        successful_uploads = sum(results)
        print(f"Test complete. Successfully uploaded {successful_uploads} out of {len(tasks)} requests over {duration_minutes} minutes.")
    except Exception as e:
        print(f"Error: {str(e)}")

async def delayed_upload(session, api_url, file_path, course_id, ingest_type, headers, delay):
    await asyncio.sleep(delay)
    return await upload_pdf(session, api_url, file_path, course_id, ingest_type, headers)

async def timed_concurrent_uploads(folder_path, base_url, course_id, ingest_type, headers, num_users=500, duration_minutes=30):
    print("Starting timed concurrent uploads test")
    try:
        if not os.path.exists(folder_path):
            print(f"Error: Folder '{folder_path}' does not exist.")
            return []

        pdf_files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]

        if not pdf_files:
            print(f"No PDF files found in '{folder_path}'.")
            return []

        pdf_files.sort()

        api_url = f"{base_url}/note/create-text-file-note"
        print(f"API URL: {api_url}")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)

        tasks = []
        for i in range(num_users):
            max_delay = (end_time - datetime.now()).total_seconds()
            if max_delay <= 0:
                print(f"Time limit reached. Stopping after {i} users.")
                break
            delay = random.uniform(0, max_delay)

            file_index = i % len(pdf_files)
            file_path = os.path.join(folder_path, pdf_files[file_index])
            
            task = asyncio.create_task(delayed_upload(api_url, file_path, course_id, ingest_type, headers, delay))
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        successful_uploads = sum(success for success, _ in results)
        response_times = [time for _, time in results]
        avg_response_time = sum(response_times) / len(response_times)
        print(f"Test complete. Successfully uploaded {successful_uploads} out of {len(tasks)} requests over {duration_minutes} minutes.")
        print(f"Average response time: {avg_response_time:.2f} seconds")
        return response_times
    except Exception as e:
        print(f"Error: {str(e)}")
        return []

async def delayed_upload(api_url, file_path, course_id, ingest_type, headers, delay):
    await asyncio.sleep(delay)
    async with aiohttp.ClientSession() as session:
        return await upload_pdf(session, api_url, file_path, course_id, ingest_type, headers)

async def ping_graph_endpoint(session, base_url, course_id, headers):
    api_url = f"{base_url}/graph/get-graph-for/courseId/{course_id}"
    start_time = datetime.now()
    try:
        async with session.get(api_url, headers=headers) as response:
            await response.text()
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            print(f"Graph ping response time: {response_time:.2f} seconds")
            return response_time
    except Exception as e:
        print(f"Error pinging graph endpoint: {str(e)}")
        return None

async def continuous_graph_pinging(base_url, course_id, headers, duration_minutes=30):
    print("Starting continuous graph pinging test")
    try:
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)

        response_times = []
        async with aiohttp.ClientSession() as session:
            while datetime.now() < end_time:
                response_time = await ping_graph_endpoint(session, base_url, course_id, headers)
                if response_time is not None:
                    response_times.append(response_time)
                await asyncio.sleep(0.5)  # Wait for 0.5 seconds before the next ping

        avg_response_time = sum(response_times) / len(response_times)
        print(f"Graph pinging test complete. Average response time: {avg_response_time:.2f} seconds")
        return response_times
    except Exception as e:
        print(f"Error in continuous graph pinging: {str(e)}")
        return []

def generate_graph(upload_times, ping_times, filename):
    plt.figure(figsize=(12, 6))
    plt.plot(upload_times, label='Upload Response Times')
    plt.plot(ping_times, label='Graph Ping Response Times')
    plt.title('Upload and Graph Ping Response Times')
    plt.xlabel('Request Number')
    plt.ylabel('Response Time (seconds)')
    plt.legend()
    plt.savefig(filename)
    plt.close()

async def run_concurrent_tests(folder_path, base_url, course_id, ingest_type, email, password, num_users=500, duration_minutes=30):
    print("Starting concurrent performance tests")
    
    async with aiohttp.ClientSession() as session:
        bearer_token = await login(session, base_url, email, password)
        if not bearer_token:
            print("Login failed. Unable to proceed with tests.")
            return

        headers = {
            'Authorization': f'Bearer {bearer_token}'
        }

        upload_task = asyncio.create_task(timed_concurrent_uploads(folder_path, base_url, course_id, ingest_type, headers, num_users, duration_minutes))
        ping_task = asyncio.create_task(continuous_graph_pinging(base_url, course_id, headers, duration_minutes))

        upload_times, ping_times = await asyncio.gather(upload_task, ping_task)

    generate_graph(upload_times, ping_times, 'concurrent_performance_graph.png')
    print("Concurrent tests complete. Graph saved as 'concurrent_performance_graph.png'")

def concurrent_performance_test():
    if not local:
        print("Running tests on server")
        asyncio.run(run_concurrent_tests(folder_path, base_url, course_id, ingest_type, email, password, num_users, duration_minutes))
    else:
        print("Running tests locally")
        asyncio.run(run_concurrent_tests(folder_path, local_url, local_course_id, ingest_type, local_email, local_password, num_users, duration_minutes))

def concurrent():
    if not local:
        print("Running on server")
        asyncio.run(simulate_concurrent_uploads(folder_path, base_url, course_id, ingest_type, email, password, num_users=num_users))
    else:
        print("Running locally")
        asyncio.run(simulate_concurrent_uploads(folder_path, local_url, local_course_id, ingest_type, local_email, local_password, num_users=num_users))

def spaced():
    if not local:
        print("Running on server")
        asyncio.run(timed_concurrent_uploads(folder_path, base_url, course_id, ingest_type, email, password, num_users=num_users, duration_minutes=duration_minutes))
    else:
        print("Running locally")
        asyncio.run(timed_concurrent_uploads(folder_path, local_url, local_course_id, ingest_type, local_email, local_password, num_users=num_users, duration_minutes=duration_minutes))


if __name__ == "__main__":
    concurrent()