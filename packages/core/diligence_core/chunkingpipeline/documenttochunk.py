import httpx
import uuid
from pydantic import AnyUrl
from pypdf import PdfReader
from typing import List, Dict, Union
from io import BytesIO
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
            "text": text.replace("\xa0", " ")  # small cleanup
        })
    return pages_list


def recursive_split(text: str, chunk_size: int, overlap: int) -> List[str]:
    separators = ["\n\n", "\n", ". ", " ", ""]

    def split(text: str, seps: List[str]) -> List[str]:
        if len(text) <= chunk_size:
            return [text]

        if not seps:
            return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

        sep = seps[0]
        parts = text.split(sep)

        chunks = []
        current = ""

        for part in parts:
            if len(current) + len(part) + len(sep) <= chunk_size:
                current += part + sep
            else:
                if current:
                    chunks.extend(split(current.strip(), seps[1:]))
                current = part + sep

        if current:
            chunks.extend(split(current.strip(), seps[1:]))

        return chunks

    base_chunks = split(text, separators)

    final_chunks = []
    for i, chunk in enumerate(base_chunks):
        if i > 0:
            prev = base_chunks[i - 1]
            chunk = prev[-overlap:] + " " + chunk
        final_chunks.append(chunk.strip())

    return final_chunks


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

    for page in pages_list:
        page_no = page["page"]
        text = page["text"]

        split_chunks = recursive_split(text, chunk_size, overlap)

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