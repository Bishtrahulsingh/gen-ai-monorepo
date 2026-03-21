import asyncio
import logging
import uuid
from typing import Iterable, AsyncGenerator, Any, List, Optional, Union
from groq import AsyncGroq, AsyncStream
from groq.types.chat import ChatCompletionMessageParam, ChatCompletion, ChatCompletionChunk

from diligence_core import settings
from diligence_core.eval_system.observability.tracer import Tracer
from diligence_core.vectordb.qdrantConfig import filter_and_search_chunks


class LLMWrapper:
    def __init__(self,max_allowed:int=10):
        self.models=['llama-3.1-8b-instant','openai/gpt-oss-20b','llama-3.3-70b-versatile','openai/gpt-oss-120b']
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self._sem = asyncio.Semaphore(max_allowed)
        self._tracer = Tracer()

    async def hyde_based_context_retrival(self,query: str, company_id: uuid.UUID, collection_name: str):
        #make a llm call for an example ans possible for best retrival
        with self._tracer.start_observation(name="hyde retrival",observation_type="span"):

            factual_signals = [
                "what is", "what was", "how much", "total",
                "exact", "give me", "what were", "revenue of",
                "earnings", "eps", "net income", "gross margin",
                "how many", "when did", "which year"
            ]

            for signal in factual_signals:
                if signal in query.lower():
                    context = await filter_and_search_chunks(collection_name=collection_name, query=query,
                                                             company_id=company_id)
                    return context


            query_messages = [
            {"role": "system", "content": """
            You are a financial analyst assistant.
    
            Given a user query, write a short hypothetical passage that might appear 
            in a 10-K SEC filing or annual report related to that topic.
        
            Rules:
            - Use formal SEC filing language and vocabulary
            - Do NOT invent specific numbers, figures, or percentages
            - Use placeholder language instead: "the company reported significant growth",
              "revenues increased year-over-year", "margins were impacted by"
            - Focus on the VOCABULARY and STRUCTURE of the answer, not the facts
            - 3-5 sentences only
        
            Your goal is to help find relevant passages — not to answer the question.
                    
            """},
            {"role": "user", "content": query},
        ]
            response = await self.client.chat.completions.create(
                messages=query_messages,
                model='llama-3.1-8b-instant'
            )

            content = response.choices[0].message.content

            context = await filter_and_search_chunks(collection_name=collection_name, query=content,
                                           company_id=company_id)
            return context

    async def fallback_completion(self,messages:Iterable[ChatCompletionMessageParam], unavailable_model:Optional[str]=None,**kwargs)->List[str]:
        available_models = list(self.models)
        if unavailable_model and unavailable_model in available_models:
            available_models.remove(unavailable_model)

        for idx,available_model in enumerate(available_models):
            judge = available_models[idx+1] if idx+1 < len(available_models) else None
            if not judge:
                break
            try:
                response = await self.make_llm_call(
                messages=messages,
                model=available_model,
                stream=False,
                **kwargs
                )

                return [judge,response.choices[0].message.content]
            except Exception as e:
                continue
        raise Exception('Model not available currently ')

    async def make_llm_call(self,messages:Iterable[ChatCompletionMessageParam],model:str,stream:bool=False,**kwargs)-> Union[ChatCompletion | AsyncStream[ChatCompletionChunk]]:
        with self._tracer.start_observation(name="llm_call", observation_type='generation'):
            response = await self.client.chat.completions.create(
                messages=messages,
                model=model,
                stream=stream,
                **kwargs
            )

            return response

    async def non_streamed_response(self,messages:Iterable[ChatCompletionMessageParam],**kwargs):
        async with self._sem:
            model = self.models[0]
            judge = self.models[1]
            try:
                response = await  self.make_llm_call(messages=messages ,model=model,stream=False,**kwargs)
                return [judge,response.choices[0].message.content]
            except Exception:
                judge,response = await self.fallback_completion(messages=messages,unavailable_model=model,**kwargs)
                if response:
                    return [judge,response]
            raise Exception('Model Attempt Failed retrying...')

    async def call_llm_streamed(self,model:str, messages:Iterable[ChatCompletionMessageParam],**kwargs)->Any:
        return await self.make_llm_call(
                    model=model,
                    messages=messages,
                    stream=True,
                    **kwargs
                )

    async def streamed_response(self,judge:str,messages:Iterable[ChatCompletionMessageParam],**kwargs)->AsyncGenerator[str,None]:
        async with self._sem:
            try:
                response = await self.call_llm_streamed(judge,messages=messages,**kwargs)
                # print(response.usage.completion_tokens, response.usage.prompt_tokens, response.usage.total_tokens,response.usage.completion_time)
                async for chunk in response:
                    token_text = chunk.choices[0].delta.content
                    if not token_text:
                        continue
                    print(token_text, end="")
                    yield token_text

            except Exception as e:
                logging.info('Model Attempt Failed retrying...')
                raise
