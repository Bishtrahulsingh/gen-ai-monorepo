from pathlib import Path

def load_prompt(name:str):
    return Path(name).read_text()