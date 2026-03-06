import httpx
import uuid
from pydantic import AnyUrl
from pypdf import PdfReader
from typing import List ,Dict, Union
from io import BytesIO

from diligence_core.schemas.chunkschema import ChunkSchema


async def read_file_bytes(file_path:AnyUrl)->bytes:
    async with httpx.AsyncClient() as client:
        response = await client.get(file_path)
        response.raise_for_status()
        file_bytes = response.content
    return file_bytes

async def read_pdf(file_path:AnyUrl)->list:
    pdf_bytes = await read_file_bytes(file_path)
    pdf_text = BytesIO(pdf_bytes)

    reader = PdfReader(pdf_text)
    pages_list = []

    for i , page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages_list.append({
            "page":i+1,
            "text": text
        })
    return pages_list

async def create_chunks(file_path:AnyUrl,user_id:uuid.UUID, document_id:uuid.UUID, company_id:uuid.UUID, chunk_size:int=500, overlap:int = 50)->List[Dict[str,Union[str,int,uuid.UUID]]]:
    pages_list = await read_pdf(file_path=file_path)
    chunks:List[Dict[str,Union[str,int,uuid.UUID]]] = []

    for page_no, page in enumerate(pages_list):
        text = page['text']
        i = 0
        count = 0

        while i<len(text):
            i = (i-overlap) if (i-overlap)>=0 else i
            end = min(i+chunk_size, len(text))
            chunk =text[i:end].strip()

            if chunk:
                chunks.append(ChunkSchema(
                    text=chunk,
                    document_id=document_id,
                    company_id=company_id,
                    page_number=page_no,
                    chunk_number=count,
                    doc_type='pdf',
                    source_url=file_path,
                    vector=[]
                    ).model_dump()
                )
                count +=1

            i += chunk_size
    return chunks


#
#
# def normalize_whitespaces(document:str)->str:
#     cleaned_document = document.replace('\r\n','\n').replace('\r','\n')
#     cleaned_document = '\n'.join(line.rstrip() for line in cleaned_document.split('\n'))
#     cleaned_document = re.sub(r'\n{3,}','\n\n',cleaned_document)
#     cleaned_document = cleaned_document.strip()
#
#     return cleaned_document
#
#
# def normalize_line_spacing(line:str)->str:
#     nl = line.strip()
#     nl = re.sub(r'\s+',' ',nl)
#     return nl
#
# def line_counter(lines:List[str])->Counter:
#     normed:List[str] = []
#     for line in lines:
#         normed_line = normalize_line_spacing(line=line)
#         if normed_line:
#             normed.append(normed_line)
#     return Counter(normed)
#
#
# def remove_table_of_contents(text: str):
#     text = normalize_whitespaces(text)
#     lines = text.split('\n')
#     for line in lines:
#         print(line)
#     in_toc = False
#
#     deleted = set()
#
#     MATCH_PART = re.compile(r'^Part\s*([IVX]+|[0-9]+|[A-Z]+)', re.IGNORECASE)
#     MATCH_ITEM = re.compile(r'^Item\s*([0-9]+[A-Z]?|[IVX]+[A-Z]?)', re.IGNORECASE)
#
#     for i, line in enumerate(lines):
#         if re.match(r'^(table of content[s]?)\s*$', line.lower().strip(), re.IGNORECASE):
#             in_toc = True
#             lines[i] = ''
#             continue
#
#         if in_toc:
#             if line.strip().lower() == '':
#                 continue
#
#             match_part = MATCH_PART.match(line)
#             match_item = MATCH_ITEM.match(line)
#             match_page = re.match(r'^Page\s*', line, re.IGNORECASE)
#
#             if match_part or match_item or match_page:
#                 matched_text = ""
#                 if match_part:
#                     matched_text = match_part.group()
#                 elif match_item:
#                     matched_text = match_item.group()
#                 else:
#                     matched_text = match_page.group()
#
#                 if matched_text not in deleted:
#                     deleted.add(matched_text)
#                     lines[i] = ''
#                     continue
#                 else:
#                     break
#
#             in_toc = False
#
#     return lines
#
#
