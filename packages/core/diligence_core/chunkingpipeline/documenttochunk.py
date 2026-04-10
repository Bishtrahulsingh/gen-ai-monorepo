import asyncio
import httpx
import uuid
import re
import fitz
import pymupdf4llm
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Pool, cpu_count
from typing import List, Dict, Union, Optional, Tuple
from pydantic import AnyUrl
from langchain_text_splitters import RecursiveCharacterTextSplitter
from io import BytesIO

from pypdf import PdfReader

from diligence_core.edgarfilefetching.accesssecfilings import FilingDetails
from diligence_core.schemas.chunkschema import ChunkSchema

_BATCH_SIZE = 40000

_UNIT_RE = re.compile(
    r'(?:'
    r'in\s+(?:thousands|millions|billions|hundreds)'
    r'(?:\s+of\s+[\w\s.,$€£]{1,30}?)?'
    r'(?:\s*,\s*except\s+(?:per\s+)?(?:share|unit|warrant|option)'
    r'(?:\s+(?:and\s+per\s+share\s+)?(?:data|amounts?|figures?|prices?|counts?))?)*'
    r'|'
    r'(?:amounts?|figures?|values?)\s+(?:are\s+)?in\s+(?:thousands|millions|billions)'
    r'(?:\s+of\s+[\w\s.,$€£]{1,30}?)?'
    r'(?:\s*,\s*except\s+(?:per\s+)?(?:share|unit)\s*(?:data|amounts?|figures?)?)*'
    r'|'
    r'(?:thousands|millions|billions)\s+of\s+(?:dollars?|USD|EUR|GBP)'
    r')',
    re.IGNORECASE,
)


def _detect_unit(text: str) -> Optional[str]:
    m = _UNIT_RE.search(text)
    return m.group(0).strip() if m else None


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
        pages_list.append({"page": i + 1, "text": text.replace("\xa0", " ")})
    return pages_list


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_TABLE_ROW_RE = re.compile(r"^\s*\|")
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s\-:|]+\|")


def _process_page_worker(args: tuple) -> Tuple[List[Dict], List[str]]:
    (
        page_bytes, page_no, file_path_str,
        document_id_str, company_id_str,
        ticker, fiscal_year,
        chunk_size, overlap,
    ) = args

    import re, fitz, pymupdf4llm
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from typing import Optional, List, Dict

    UNIT_RE = re.compile(
        r'(?:'
        r'in\s+(?:thousands|millions|billions|hundreds)'
        r'(?:\s+of\s+[\w\s.,$€£]{1,30}?)?'
        r'(?:\s*,\s*except\s+(?:per\s+)?(?:share|unit|warrant|option)'
        r'(?:\s+(?:and\s+per\s+share\s+)?(?:data|amounts?|figures?|prices?|counts?))?)*'
        r'|'
        r'(?:amounts?|figures?|values?)\s+(?:are\s+)?in\s+(?:thousands|millions|billions)'
        r'(?:\s*,\s*except\s+(?:per\s+)?(?:share|unit)\s*(?:data|amounts?))?'
        r'|'
        r'(?:thousands|millions|billions)\s+of\s+(?:dollars?|USD|EUR|GBP)'
        r')',
        re.IGNORECASE,
    )
    HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
    TABLE_ROW_RE = re.compile(r"^\s*\|")

    def detect_unit(text: str) -> Optional[str]:
        m = UNIT_RE.search(text)
        return m.group(0).strip() if m else None

    page_doc = fitz.open(stream=page_bytes, filetype="pdf")
    md = pymupdf4llm.to_markdown(page_doc, pages=[0])
    page_doc.close()

    page_unit: Optional[str] = detect_unit(md)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        strip_whitespace=True,
    )

    raw_chunks: List[Dict] = []
    headings: List[str] = []
    seen_headings: set = set()

    current_heading: Optional[str] = None
    heading_level: int = 0
    heading_stack: List[tuple] = []

    buffer: List[str] = []
    table_lines: List[str] = []
    pre_table_ctx: List[str] = []
    in_table = False

    def resolve_heading() -> Optional[str]:
        if not heading_stack:
            return None
        return " > ".join(h for _, h in heading_stack)

    def make_base_chunk(is_table: bool, unit: Optional[str]) -> Dict:
        return {
            "page_number": page_no,
            "heading":     resolve_heading(),
            "is_table":    is_table,
            "unit":        unit,
            "source_url":  f"{file_path_str}#page={page_no}",
            "document_id": document_id_str,
            "company_id":  company_id_str,
            "ticker":      ticker,
            "fiscal_year": fiscal_year,
            "doc_type":    "pdf",
        }

    def flush_text():
        text = "\n".join(buffer).strip()
        buffer.clear()
        if not text:
            return
        heading_label = resolve_heading()
        heading_tag = f"[{heading_label}]\n" if heading_label else ""
        local_unit = detect_unit(text) or page_unit
        unit_tag = f"[units: {local_unit}]" if local_unit else "[units: not specified]"
        for sub in splitter.split_text(text):
            chunk = make_base_chunk(is_table=False, unit=local_unit)
            chunk["text"] = f"{heading_tag}{unit_tag}\n{sub}"
            raw_chunks.append(chunk)

    def flush_table():
        table_text = "\n".join(table_lines).strip()
        table_lines.clear()
        if not table_text:
            return
        local_ctx = "\n".join(pre_table_ctx[-6:]) + "\n" + table_text[:500]
        unit = detect_unit(local_ctx) or page_unit
        heading_label = resolve_heading()
        heading_tag = f"[{heading_label}]\n" if heading_label else ""
        unit_tag = f"[units: {unit}]" if unit else "[units: not specified]"
        chunk = make_base_chunk(is_table=True, unit=unit)
        chunk["text"] = f"[table]\n{heading_tag}{unit_tag}\n{table_text}"
        raw_chunks.append(chunk)

    for line in md.splitlines():
        heading_match = HEADING_RE.match(line)

        if heading_match:
            if in_table:
                flush_table()
                in_table = False
            flush_text()

            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            heading_stack = [(l, h) for l, h in heading_stack if l < level]
            heading_stack.append((level, title))

            current_heading = title
            heading_level = level

            if title not in seen_headings:
                seen_headings.add(title)
                headings.append(title)

            pre_table_ctx.clear()
            continue

        if TABLE_ROW_RE.match(line):
            if not in_table:
                flush_text()
                in_table = True
            table_lines.append(line)
        else:
            if in_table:
                flush_table()
                in_table = False
            buffer.append(line)
            pre_table_ctx.append(line)
            if len(pre_table_ctx) > 10:
                pre_table_ctx.pop(0)

    if in_table:
        flush_table()
    flush_text()

    return raw_chunks, headings


async def create_chunks(
    file_path: AnyUrl,
    document_id: uuid.UUID,
    company_id: uuid.UUID,
    ticker: str,
    fiscal_year: int,
    chunk_size: int = 1200,
    overlap: int = 80,
) -> Tuple[List[Dict[str, Union[str, int, uuid.UUID]]], List[str]]:
    if str(file_path).startswith(("http://", "https://")):
        async with httpx.AsyncClient() as client:
            resp = await client.get(str(file_path))
            resp.raise_for_status()
        pdf_bytes = resp.content
    else:
        with open(str(file_path), "rb") as f:
            pdf_bytes = f.read()

    master = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_args = []
    for i in range(len(master)):
        single = fitz.open()
        single.insert_pdf(master, from_page=i, to_page=i)
        page_args.append((
            single.tobytes(),
            i + 1,
            str(file_path),
            str(document_id),
            str(company_id),
            ticker,
            fiscal_year,
            chunk_size,
            overlap,
        ))
        single.close()
    master.close()

    loop = asyncio.get_event_loop()
    workers = min(cpu_count(), len(page_args))

    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = await asyncio.gather(*[
            loop.run_in_executor(executor, _process_page_worker, args)
            for args in page_args
        ])

    all_chunks: List[Dict] = []
    all_headings: List[str] = []
    seen_headings: set = set()

    for raw_chunks, page_headings in results:
        for c in raw_chunks:
            all_chunks.append(
                ChunkSchema(
                    text=c["text"],
                    document_id=uuid.UUID(c["document_id"]),
                    company_id=uuid.UUID(c["company_id"]),
                    ticker=c["ticker"],
                    fiscal_year=c["fiscal_year"],
                    page_number=c["page_number"],
                    chunk_number=len(all_chunks),
                    doc_type=c["doc_type"],
                    source_url=c["source_url"],
                    vector=[],
                ).model_dump()
            )
        for h in page_headings:
            if h not in seen_headings:
                seen_headings.add(h)
                all_headings.append(h)

    return all_chunks, all_headings


async def create_chunks_for_structured_data(
    metadata: FilingDetails,
    sections: dict,
    chunk_size: int = 1000,
    overlap: int = 250,
) -> Tuple[List[Dict[str, Union[str, int, uuid.UUID]]], Dict[str, List[str]]]:
    chunks = []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        strip_whitespace=True,
    )
    for section, content in sections.items():
        for text in splitter.split_text(content):
            if len(text) < 50:
                continue
            chunk = {**dict(metadata)}
            chunk["text"] = text
            chunk["heading"] = section
            chunks.append(chunk)

    return chunks, {}