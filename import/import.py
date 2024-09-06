import os
from dotenv import load_dotenv
import csv
import supabase
from constants import CHAT_TABLE_NAME, COURSE_TABLE_NAME, COLLEGE_ID

load_dotenv()

supabase_client = supabase.create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

def import_courses(file_path='courses.csv', limit=5):
    """
    Load courses from the courses.csv file in the current dir
    For each row in courses (after the header):
        Create a course with supabase in the COURSE_TABLE_NAME table
        Create a chatroom with supabase in the CHAT_TABLE_NAME table
    """
    imported_count = 0
    
    with open(file_path, 'r') as file:
        csv_reader = csv.reader(file, delimiter='<')
        next(csv_reader)
        
        for row in csv_reader:
            # if imported_count >= limit:
            #     break
            
            course_data = {
                "courseNumber": row[0],
                "name": row[1],
                "description": row[2],
                "collegeId": COLLEGE_ID
            }
            
            print(f"Importing course: {course_data}")

            course_response = supabase_client.table(COURSE_TABLE_NAME).insert(course_data).execute()
            
            if len(course_response.data) > 0:
                course_id = course_response.data[0]['id']
                
                chat_data = {
                    "courseId": course_id,
                    "public": True
                }
                supabase_client.table(CHAT_TABLE_NAME).insert(chat_data).execute()
                
                imported_count += 1
                print(f"Imported course: {course_data['name']}")
            else:
                print(f"Failed to import course: {course_data['name']}")
    
    print(f"Import complete. {imported_count} courses imported.")

if __name__ == "__main__":
    import_courses()