from typing import List , Dict

class TokenCounter:
    def __init__(self, model:str):
        self.model = model
        self.counter = 0

    def get_text(self,messages:List[Dict[str]])->str:
        text = "\n".join(message['content'] for message in messages)
        return text or ""

    def count_tokens(self,text:str)->int:
        return 0