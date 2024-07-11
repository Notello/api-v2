from langchain_core.documents import Document

def clean_file(pages):
    bad_chars = ['"', "\n", "'"]
    for i in range(0,len(pages)):
        text = pages[i].page_content
        for j in bad_chars:
            if j == '\n':
                text = text.replace(j, ' ')
            else:
                text = text.replace(j, '')
        
        pages[i] = Document(page_content=str(text), metadata=pages[i].metadata)