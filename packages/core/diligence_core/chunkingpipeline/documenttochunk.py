from pypdf import PdfReader
from typing import List ,Dict, Union
import io
import uuid

def read_file_bytes(file_path):
    with open(file_path, 'rb') as f:
        file_bytes = f.read()
    return file_bytes

def read_pdf(file_path):
    file_bytes = read_file_bytes(file_path)

    reader = PdfReader(io.BytesIO(file_bytes))
    pages_list = []

    for i , page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages_list.append({
            "page":i+1,
            "text": text
        })
    return pages_list


def create_chunks(pages_list:List[Dict[str,Union[str,int]]], user_id:uuid.UUID, doc_id:uuid.UUID, org_id:uuid.UUID, case_id:uuid.UUID, chunk_size:int=500, overlap:int = 50)->List[Dict[str,Union[str,int,uuid.UUID]]]:
    chunks:List[Dict[str,Union[str,int,uuid.UUID]]] = []
    for page in pages_list:
        chunk = ''
        text = page['text']
        i = 0
        while i<len(text):
            i = (i-overlap) if (i-overlap)>=0 else i
            end = min(i+chunk_size, len(text))
            chunk =text[i:end].strip()

            if chunk:
                chunks.append({
                    "doc_id":doc_id,
                    "user_id":user_id,
                    "case_id":case_id,
                    "org_id": org_id,
                    "page":page['page'],
                    "start":i,
                    "end": end,
                    "text":chunk
                })

            i += chunk_size
    return chunks
