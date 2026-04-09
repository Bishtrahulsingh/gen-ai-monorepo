from pathlib import Path
from typing import List, Dict, Any, Tuple

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text()


def chunk_to_str(chunks: List[Any]) -> str:
    """Render chunks as indexed text for the LLM prompt."""
    text_with_id = ''
    for idx, chunk in enumerate(chunks):
        text_with_id += f"[chunk_{idx}]:{chunk}\n"
    return text_with_id


def build_chunk_metadata_map(chunks: List[Any]) -> Dict[int, Dict]:
    mapping: Dict[int, Dict] = {}
    for idx, chunk in enumerate(chunks):
        payload = chunk.get('payload', chunk)  # handle both raw dict and Qdrant payload
        mapping[idx] = {
            'source_url':  str(payload.get('source_url', '')),
            'page_number': payload.get('page_number', 1),
            'document_id': str(payload.get('document_id', '')),
            'ticker':      payload.get('ticker', ''),
            'fiscal_year': payload.get('fiscal_year', ''),
        }
    return mapping


def replace_input_values(
    template: str,
    company_name: str,
    retrieved_chunks: str,
    user_question: str,
) -> str:
    return (
        template
        .replace("{{company_name}}", company_name)
        .replace("{{retrieved_chunks}}", retrieved_chunks)
        .replace("{{user_question}}", user_question)
    )