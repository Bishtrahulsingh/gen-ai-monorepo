import asyncio
import os
import random
from typing import Iterable
from tenacity import retry, stop_after_attempt, wait_exponential
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

    async def complete(self,messages:Iterable[ChatCompletionMessageParam],**kwargs)->str:
        return await self.call_model(messages=messages,**kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def call_model(self,messages:Iterable[ChatCompletionMessageParam],**kwargs)->str:
        async with self._sem:
            model = self.choose_model()
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            print(response.usage.completion_tokens, response.usage.prompt_tokens, response.usage.total_tokens,response.usage.completion_time)

            return response.choices[0].message.content or ""

