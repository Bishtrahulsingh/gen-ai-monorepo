import asyncio
from typing import Iterable, AsyncGenerator, Any, List, Optional
from groq import AsyncGroq
from groq.types.chat import ChatCompletionMessageParam

from diligence_analyst.prompts.p1_memo.load_prompt import load_prompt
from diligence_core import settings

class LLMWrapper:
    def __init__(self,max_allowed:int=10):
        self.models=['llama-3.1-8b-instant','openai/gpt-oss-20b','llama-3.3-70b-versatile','openai/gpt-oss-120b']
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self._sem = asyncio.Semaphore(max_allowed)

    async def fallback_completion(self,messages:Iterable[ChatCompletionMessageParam], unavailable_model:Optional[str]=None,**kwargs)->List[str]:
        available_models = list(self.models)
        if unavailable_model and unavailable_model in available_models:
            available_models.remove(unavailable_model)

        for idx,available_model in enumerate(available_models):
            judge = available_models[idx+1] if idx+1 < len(available_models) else None
            if not judge:
                break
            try:
                response = await self.client.chat.completions.create(
                messages=messages,
                model=available_model,
                stream=False,
                **kwargs
                )

                return [judge,response.choices[0].message.content]
            except Exception as e:
                continue
        raise Exception('Model not available currently ')

    async def non_streamed_response(self,messages:Iterable[ChatCompletionMessageParam],**kwargs):
        async with self._sem:
            model = self.models[0]
            judge = self.models[1]
            try:
                response = await self.client.chat.completions.create(
                    messages=messages,
                    model=model,
                    stream=False,
                    **kwargs
                )

                return [judge,response.choices[0].message.content]
            except Exception:
                judge,response = await self.fallback_completion(messages=messages,unavailable_model=model,**kwargs)
                if response:
                    return [judge,response]
            raise Exception('Model Attempt Failed retrying...')

    async def call_llm_streamed(self,model:str, messages:Iterable[ChatCompletionMessageParam],**kwargs)->Any:
        return await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    **kwargs
                )

    async def streamed_response(self,messages:Iterable[ChatCompletionMessageParam],**kwargs)->Optional[AsyncGenerator[str,None]]:
        async with self._sem:
            try:
                judge,raw_response = await self.non_streamed_response(messages=messages,**kwargs)

                judge_system_prompt = load_prompt('system_template_judge.md')

                messages = [
                    {'role':'system','content':judge_system_prompt },
                    {'role':'user','content':raw_response}
                ]

                response = await self.call_llm_streamed(judge,messages=messages,**kwargs)
                # print(response.usage.completion_tokens, response.usage.prompt_tokens, response.usage.total_tokens,response.usage.completion_time)
                async for chunk in response:
                    token_text = chunk.choices[0].delta.content
                    if not token_text:
                        continue
                    print(token_text, end="")
                    yield token_text

            except Exception as e:
                print(e)
                print('Model Attempt Failed retrying...')
                raise
