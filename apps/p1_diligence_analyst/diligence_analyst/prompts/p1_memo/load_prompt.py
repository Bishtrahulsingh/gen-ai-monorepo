from pathlib import Path
from typing import List

def load_prompt(name:str):
    path = f"apps/p1_diligence_analyst/diligence_analyst/prompts/p1_memo/{name}"
    return Path(path).read_text()

def chunk_to_str(chunks:List['str']):
    text_with_id = ''

    for idx, chunk in enumerate(chunks):
        text_with_id += f"[chunk_{idx}]:{chunk}\n"
    return text_with_id

def replace_input_values(template:str, company_name:str, retrieved_chunks:str, user_question:str):
    return template.replace("{{company_name}}", company_name).replace("{{retrieved_chunks}}", retrieved_chunks).replace("{{user_question}}", user_question)