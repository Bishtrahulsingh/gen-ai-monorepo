import asyncio
import random
import time
from typing import Iterable, AsyncGenerator, Any, Optional

from httpx import stream
from tenacity import retry, stop_after_attempt, wait_random_exponential
from groq import AsyncGroq
from groq.types.chat import ChatCompletionMessageParam
from diligence_core import settings

class LLMWrapper:
    def __init__(self,max_allowed:int=10):
        self.weighted_models = {
            "openai/gpt-oss-20b": 0.45,
            "qwen/qwen3-32b": 0.25,
            "llama-3.3-70b-versatile": 0.15,
            "mixtral-8x7b-32768": 0.10,
            "gemma-7b-it": 0.05
        }
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self._sem = asyncio.Semaphore(max_allowed)

    def choose_model(self)->str:
        models = list(self.weighted_models.keys())
        weights = list(self.weighted_models.values())
        return random.choices(models,weights)[0]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, max=8),
        reraise=True
    )
    async def streamed_response(self,messages:Iterable[ChatCompletionMessageParam],**kwargs)->Any:
        async with self._sem:
            model = self.choose_model()
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    **kwargs
                )
                # print(response.usage.completion_tokens, response.usage.prompt_tokens, response.usage.total_tokens,response.usage.completion_time)
                async for chunk in response:
                    print(chunk, end='\n\n\n')
                    token_text = chunk.choices[0].delta.content
                    if not token_text:
                        continue
                    yield token_text

            except Exception as e:
                print(e)
                print('Model Attempt Failed retrying...')
                raise
