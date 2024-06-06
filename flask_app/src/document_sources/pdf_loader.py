from io import BytesIO
import PyPDF2
import logging
from werkzeug.datastructures import FileStorage
import tempfile
import os


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
        print("error pdf", file)
        logging.exception(f'Exception for file: {file.filename}, Stack trace: {e}')
        return None