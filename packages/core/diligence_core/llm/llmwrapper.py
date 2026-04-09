import asyncio
import json
import logging
import re
from typing import Iterable, AsyncGenerator, Any, List
from groq import AsyncGroq
from groq.types.chat import ChatCompletionMessageParam

from diligence_core import settings
from diligence_core.eval_system.observability.tracer import Tracer
from diligence_core.vectordb.qdrantConfig import filter_and_search_chunks


class LLMWrapper:
    def __init__(self, max_allowed: int = 10):
        self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.groq_models = [
            'llama-3.1-8b-instant',
            'llama-3.3-70b-versatile',
            'llama-3.1-70b-versatile',
            'llama3-70b-8192',
            'openai/gpt-4o-mini',
            'openai/gpt-4o',
        ]

        self._sem = asyncio.Semaphore(max_allowed)
        self._tracer = Tracer()

    def _get_model(self, model: str) -> str:

        if "::" in model:
            _, clean_model = model.split("::", 1)
            return clean_model
        return model

    async def hyde_based_context_retrival(
        self, query: str, collection_name: str, token: str, ticker: str, fiscal_year: int
    ):
        with self._tracer.start_observation(name="hyde retrival", observation_type="span"):
            query_messages = [
                {
                    "role": "system",
                    "content": """
            You generate search queries for retrieving passages from SEC 10-K filings.

            Rules:

            1. If the query asks for a specific number, metric, or factual value
               (e.g., revenue, net income, assets, liabilities, dates),
               return only the original query.

            2. If the query is conceptual, analytical, or about risks, causes,
               trends, or explanations, generate two additional expanded queries
               using financial and accounting terminology commonly used in SEC filings.

            3. Preserve the original meaning of the query.

            4. Keep queries concise (one sentence each).

            Return the result as a JSON array of queries.
            """
                },
                {
                    "role": "user",
                    "content": query
                }
            ]

            content = await self.make_llm_call(
                messages=query_messages,
                model=self.groq_models[0],
                parse_json=False,
            )

            raw_content = content.choices[0].message.content

            context = await filter_and_search_chunks(
                collection_name=collection_name, query=raw_content,
                ticker=ticker, fiscal_year=fiscal_year,
            )

            return context

    async def groq_fallback_completion(
        self,
        messages: Iterable[ChatCompletionMessageParam],
        parse_json: bool = False,
        **kwargs,
    ) -> List[str]:
        kwargs.pop("response_format", None)

        for idx, model in enumerate(self.groq_models):
            judge = self.groq_models[idx + 1] if idx + 1 < len(self.groq_models) else None
            if not judge:
                break
            try:
                logging.info(f"[Groq fallback] trying {model}")
                groq_kwargs = dict(kwargs)
                if parse_json:
                    groq_kwargs.setdefault("response_format", {"type": "json_object"})
                response = await self.groq_client.chat.completions.create(
                    model=model,
                    messages=list(messages),
                    **groq_kwargs,
                )
                content = response.choices[0].message.content
                logging.info(f"[Groq fallback] succeeded with {model}")
                return [f"groq::{judge}", content]
            except Exception as e:
                logging.warning(f"[Groq fallback] {model} failed: {e}")
                continue

        raise Exception("All Groq models failed. No further fallback available.")

    async def make_llm_call(
        self,
        messages: Iterable[ChatCompletionMessageParam],
        model: str,
        stream: bool = False,
        parse_json: bool = True,
        **kwargs,
    ) -> Any:
        with self._tracer.start_observation(name="llm_call", observation_type="generation"):
            try:
                call_kwargs = dict(kwargs)
                if parse_json and not stream:
                    call_kwargs.setdefault("response_format", {"type": "json_object"})

                clean_model = self._get_model(model)
                logging.info(f"[Groq] using {clean_model}")
                response = await self.groq_client.chat.completions.create(
                    messages=list(messages),
                    model=clean_model,
                    stream=stream,
                    **call_kwargs,
                )
                self._tracer.update_trace(input=messages, output=response)
                if parse_json and not stream:
                    return self._extract_json(response)
                return response

            except Exception as e:
                logging.warning(f"[Groq] {model} failed: {e}. Falling back within Groq.")
                judge, response_content = await self.groq_fallback_completion(
                    messages, parse_json=parse_json, **kwargs
                )
                self._tracer.update_trace(input=messages, output=response_content)
                if parse_json and not stream:
                    return self._extract_json(_FakeCompletion(judge, response_content))
                return _FakeCompletion(judge, response_content)

    def _extract_json(self, response) -> Any:
        raw = response.choices[0].message.content or ""
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.DOTALL)

        def try_parse(text: str) -> Any:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
            try:
                fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
            match = re.search(r"(\{.*}|\[.*])", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', match.group(1))
                    return json.loads(fixed)
            raise ValueError(f"Could not extract JSON from response: {raw!r}")

        return try_parse(cleaned)

    async def non_streamed_response(
        self, messages: Iterable[ChatCompletionMessageParam], parse_json: bool = True, **kwargs
    ):
        async with self._sem:
            primary_model = self.groq_models[0]
            judge = f"groq::{self.groq_models[1]}"
            try:
                response = await self.make_llm_call(
                    messages=messages, model=primary_model,
                    stream=False, parse_json=parse_json, **kwargs
                )
                return [judge, response]
            except Exception as e:
                logging.warning(f"[non_streamed_response] make_llm_call failed: {e}. Running full fallback.")
                judge, response_content = await self.groq_fallback_completion(
                    messages=messages, parse_json=parse_json, **kwargs
                )
                if response_content:
                    if parse_json:
                        parsed = self._extract_json(_FakeCompletion(judge, response_content))
                        return [judge, parsed]
                    return [judge, response_content]
            raise Exception("All Groq model attempts failed.")

    async def streamed_response(
        self, judge: str, messages: Iterable[ChatCompletionMessageParam], **kwargs
    ) -> AsyncGenerator[str, None]:
        async with self._sem:
            try:
                clean_kwargs = {k: v for k, v in kwargs.items() if k != "response_format"}
                clean_model = self._get_model(judge)
                stream = await self.groq_client.chat.completions.create(
                    model=clean_model,
                    messages=list(messages),
                    stream=True,
                    **clean_kwargs,
                )
                async for chunk in stream:
                    token_text = chunk.choices[0].delta.content
                    if not token_text:
                        continue
                    yield token_text

            except Exception as e:
                logging.warning(f"[Streamed] Groq model failed: {e}")
                raise


class _FakeCompletion:
    def __init__(self, judge: str, content: str):
        self.choices = [_FakeChoice(content)]
        self._judge = judge


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content