import pytest
import requests
import uuid
from typing import Dict, Any
from constants import *

RANDOM_TEXT = "random_text_123"
EMPTY_TEXT = ""
NORMAL_TEXT = "This is a normal paragraph for testing purposes."
# LONG_TEXT = "A" * (5 * 1024 * 1026)  # 5 MB of text

@pytest.fixture(scope="module")
def auth_token():
    response = requests.get(f"{AUTH_ENDPOINT}/{EMAIL}/{PASSWORD}")
    assert response.status_code == 200
    return response.json()

@pytest.fixture(scope="module")
def headers(auth_token):
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

def make_api_call(headers: Dict[str, str], data: Dict[str, Any]) -> requests.Response:
    return requests.post(CREATE_TEXT_NOTE_ENDPOINT, headers=headers, data=data)

@pytest.fixture(scope="module")
def created_note_id(headers):
    data = {
        "rawText": NORMAL_TEXT,
        "ingestType": "create",
        "noteName": "Test Note",
        "courseId": VALID_COURSE_ID,
    }
    response = make_api_call(headers, data)
    assert response.status_code == 201
    return response.json()["noteId"]

@pytest.mark.parametrize("raw_text", [EMPTY_TEXT, NORMAL_TEXT, "AASASASASASASASASASAS"])
@pytest.mark.parametrize("ingest_type", ["create", "edit", RANDOM_TEXT, ""])
@pytest.mark.parametrize("note_name", ["Normal Name", "", "A" * 1000])
@pytest.mark.parametrize("course_id", [VALID_COURSE_ID, INVALID_UUID, "", RANDOM_TEXT])
def test_create_text_note(headers, raw_text, ingest_type, note_name, course_id):
    data = {
        "rawText": raw_text,
        "ingestType": ingest_type,
        "noteName": note_name,
        "courseId": course_id,
    }
    
    response = make_api_call(headers, data)
    
    # Basic checks
    assert response.status_code in [200, 201, 400, 401, 403, 404, 500]
    
    if response.status_code in [200, 201]:
        assert "noteId" in response.json()
    elif response.status_code == 400:
        assert "message" in response.json()
        assert response.json()["message"] == "Invalid inputs"
    
    # Additional checks based on input combinations
    if ingest_type not in ["create", "edit"]:
        assert response.status_code == 400
    
    if not note_name:
        assert response.status_code == 400
    
    if course_id not in [VALID_COURSE_ID, ""]:
        assert response.status_code == 400

def test_edit_text_note(headers, created_note_id):
    edit_data = {
        "rawText": "Updated text",
        "ingestType": "edit",
        "noteName": "Updated Test Note",
        "courseId": VALID_COURSE_ID,
        "noteId": created_note_id,
    }
    
    edit_response = make_api_call(headers, edit_data)
    assert edit_response.status_code == 200
    assert edit_response.json()["noteId"] == created_note_id

@pytest.mark.parametrize("note_id", [INVALID_UUID, "", RANDOM_TEXT])
def test_edit_with_invalid_note_id(headers, note_id):
    edit_data = {
        "rawText": "Updated text",
        "ingestType": "edit",
        "noteName": "Updated Test Note",
        "courseId": VALID_COURSE_ID,
        "noteId": note_id,
    }
    
    edit_response = make_api_call(headers, edit_data)
    assert edit_response.status_code == 400

def test_invalid_auth():
    invalid_headers = {
        "Authorization": "Bearer invalid_token",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    
    data = {
        "rawText": NORMAL_TEXT,
        "ingestType": "create",
        "noteName": "Test Note",
        "courseId": VALID_COURSE_ID,
    }
    
    response = make_api_call(invalid_headers, data)
    assert response.status_code in [401, 403]

if __name__ == "__main__":
    pytest.main([__file__])