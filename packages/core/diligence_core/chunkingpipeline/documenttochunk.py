import httpx
import uuid
from pydantic import AnyUrl
from pypdf import PdfReader
from typing import List, Dict, Union
from io import BytesIO

from langchain_text_splitters import RecursiveCharacterTextSplitter

from diligence_core.edgarfilefetching.accesssecfilings import FilingDetails
from diligence_core.schemas.chunkschema import ChunkSchema


async def read_file_bytes(file_path: AnyUrl) -> bytes:
    async with httpx.AsyncClient() as client:
        response = await client.get(file_path)
        response.raise_for_status()
        return response.content


async def read_pdf(file_path: AnyUrl) -> list:
    pdf_bytes = await read_file_bytes(file_path)
    reader = PdfReader(BytesIO(pdf_bytes))

    pages_list = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages_list.append({
            "page": i + 1,
            "text": text.replace("\xa0", " ")
        })
    return pages_list


async def create_chunks(
    file_path: AnyUrl,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
    company_id: uuid.UUID,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[Dict[str, Union[str, int, uuid.UUID]]]:

    pages_list = await read_pdf(file_path=file_path)
    chunks: List[Dict[str, Union[str, int, uuid.UUID]]] = []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        strip_whitespace=True
    )

    for page in pages_list:
        page_no = page["page"]
        text = page["text"]

        split_chunks = splitter.split_text(text)

        for count, chunk in enumerate(split_chunks):
            chunks.append(
                ChunkSchema(
                    text=chunk,
                    document_id=document_id,
                    company_id=company_id,
                    page_number=page_no,
                    chunk_number=count,
                    doc_type='pdf',
                    source_url=str(file_path) + f"#page={page_no}",
                    vector=[]
                ).model_dump()
            )

    return chunks


async def create_chunks_for_structured_data(
    metadata: FilingDetails,
    sections: dict,
    chunk_size: int = 800,
    overlap: int = 80
) -> List[Dict[str, Union[str, int, uuid.UUID]]]:

    print(metadata.company_name)
    chunks = []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        strip_whitespace=True
    )

    for section in sections:
        for text in sections[section].split("\n\n"):
            if len(text)<50:
                continue

            chunk = {**dict(metadata)}
            chunk['text'] = text
            chunk['heading'] = section
            chunks.append(chunk)

    for chunk in chunks:
        print(chunk, end="\n\n------------------------")

    return chunks

