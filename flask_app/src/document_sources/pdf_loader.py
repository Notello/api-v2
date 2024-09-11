from io import BytesIO
import io
import PyPDF2
import logging
from werkzeug.datastructures import FileStorage
import tempfile
import os
from bs4 import BeautifulSoup
import markdown
from langchain_community.document_loaders import UnstructuredPowerPointLoader
from langchain_community.document_loaders import Docx2txtLoader



def extract_text_from_pdf(file_content, file_name) -> str | None:
    file = FileStorage(stream=BytesIO(file_content), filename=file_name, content_type='application/pdf')
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(file.read())
            tmp_file_path = tmp_file.name

        text = ""

        with open(tmp_file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"

        os.remove(tmp_file_path)

        return text

    except Exception as e:
        logging.exception(f'Exception for file: {file_name}, Stack trace: {e}')
        return None


def extract_text_from_md(file_content, file_name) -> str | None:
    try:
        text = file_content.decode('utf-8')
        html = markdown.markdown(text)
        return html
    except Exception as e:
        logging.exception(f'Exception for file: {file_name}, Stack trace: {e}')
        return None


def extract_text_from_html(file_content, file_name) -> str | None:
    try:
        text = file_content.decode('utf-8')
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text()
    except Exception as e:
        logging.exception(f'Exception for file: {file_name}, Stack trace: {e}')
        return None
    
def extract_text_from_docx(file_content, file_name) -> str | None:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        loader = Docx2txtLoader(temp_file_path)
        data = loader.load()
        content = "".join([page.page_content for page in data])

        os.unlink(temp_file_path)

        return content
    except Exception as e:
        logging.exception(f'Exception for file: {file_name}, Stack trace: {e}')
        return None

def extract_text_from_pptx(file_content, file_name) -> str | None:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pptx') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        loader = UnstructuredPowerPointLoader(temp_file_path)
        data = loader.load()
        content = "".join([page.page_content for page in data])

        os.unlink(temp_file_path)

        return content
    except Exception as e:
        logging.exception(f'Exception for file: {file_name}, Stack trace: {e}')
        return None


def extract_text(file_content, file_name, content_type) -> str | None:
    if content_type == 'application/pdf':
        return extract_text_from_pdf(file_content, file_name)
    elif content_type == 'text/markdown':
        return extract_text_from_md(file_content, file_name)
    elif content_type == 'text/html':
        return extract_text_from_html(file_content, file_name)
    elif content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        return extract_text_from_docx(file_content, file_name)
    elif content_type == 'application/vnd.openxmlformats-officedocument.presentationml.presentation':
        return extract_text_from_pptx(file_content, file_name)
    else:
        logging.error(f'Unsupported content type: {content_type}')
        return None