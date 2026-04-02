import asyncio
import json
import logging
import re
from typing import Iterable, AsyncGenerator, Any, List, Optional, Union
from groq import AsyncGroq, AsyncStream
from groq.types.chat import ChatCompletionMessageParam, ChatCompletion, ChatCompletionChunk
from openai import AsyncOpenAI

from diligence_core import settings
from diligence_core.eval_system.observability.tracer import Tracer
from diligence_core.supabaseconfig import supabaseconfig
from diligence_core.vectordb.qdrantConfig import filter_and_search_chunks


class LLMWrapper:
    def __init__(self, max_allowed: int = 10):
        self.gemini_client = AsyncOpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=settings.GEMINI_API_KEY,
        )
        self.gemini_models = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
        ]

        self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.groq_models = [
            'llama-3.1-8b-instant',
            'llama-3.3-70b-versatile',
            'llama-3.1-70b-versatile',
            'llama3-70b-8192',
            'openai/gpt-4o-mini',
            'openai/gpt-4o',
        ]

        self.nim_client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=settings.NVIDIA_NIM_API_KEY,
        )
        self.nim_models = [
            "meta/llama-3.1-8b-instruct",
            "meta/llama-3.2-3b-instruct",
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-405b-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "deepseek-ai/deepseek-r1-distill-llama-8b",
            "deepseek-ai/deepseek-r1-distill-qwen-32b",
            "deepseek-ai/deepseek-v3.2",
            "mistralai/mixtral-8x22b-instruct-v0.1",
            "google/gemma-2-27b-it",
            "ibm/granite-3_3-8b-instruct",
        ]

        self._sem = asyncio.Semaphore(max_allowed)
        self._tracer = Tracer()

    def _get_client_and_model(self, model: str):
        if "::" in model:
            provider, clean_model = model.split("::", 1)
            if provider == "gemini":
                return self.gemini_client, clean_model
            elif provider == "groq":
                return self.groq_client, clean_model
            elif provider == "nim":
                return self.nim_client, clean_model

        if model.startswith("gemini"):
            return self.gemini_client, model
        if model in self.groq_models:
            return self.groq_client, model
        return self.nim_client, model

    async def hyde_based_context_retrival(
        self, query: str, collection_name: str, token: str, ticker: str, fiscal_year: int
    ):
        supabase_client = supabaseconfig.supabase_client
        with self._tracer.start_observation(name="hyde retrival", observation_type="span"):
            res = await (
                supabase_client
                .postgrest
                .auth(token)
                .from_("companies")
                .select("id, keywords")
                .eq("ticker", ticker.upper())
                .eq("fiscal_year", fiscal_year)
                .limit(1)
                .execute()
            )

            keywords = res.data[0]["keywords"] if res.data else []

            query_messages = [
                {
                    "role": "system",
                    "content": f"""You are a retrieval synthesizer for SEC 10-K filings.

            Write a short hypothetical passage that looks like it came from a real 10-K filing.
            This is for vector search retrieval — not to answer the user's question.

            Before writing, identify:
            1. PRIMARY SECTION — pick the single best match from: {keywords}
            2. SECONDARY SECTIONS — up to 2 others from the same list (only if helpful)
            3. TONE — match the section style:
               - Narrative: "the Company believes", "intends to", "has positioned"
               - Risk/Legal: "may", "could", "there can be no assurance"
               - MD&A: "compared to the prior period", "reflects", "was primarily driven by"

            Write 4-6 sentences in formal SEC prose.

            Never include: numbers, percentages, named products/competitors,
            restated questions, or any explanation outside the passage.

            Return only the passage."""
                },
                {
                    "role": "user",
                    "content": query
                },
            ]

            response = await self.make_llm_call(
                messages=query_messages,
                model="gemini-2.5-flash",
                parse_json=False,
            )

            content = response.choices[0].message.content
            context = await filter_and_search_chunks(
                collection_name=collection_name, query=content,
                ticker=ticker, fiscal_year=fiscal_year,
            )
            return context

    async def nim_fallback_completion(
        self,
        messages: Iterable[ChatCompletionMessageParam],
        parse_json: bool = False,
        **kwargs,
    ) -> List[str]:
        nim_kwargs = {k: v for k, v in kwargs.items() if k != "response_format"}

        patched_messages = list(messages)
        if parse_json:
            patched_messages = [
                {
                    "role": "system",
                    "content": "Respond with valid JSON only. No markdown, no code blocks, no explanation.",
                },
                *patched_messages,
            ]

        for idx, model in enumerate(self.nim_models):
            judge = self.nim_models[idx + 1] if idx + 1 < len(self.nim_models) else None
            if not judge:
                break
            try:
                logging.info(f"[NIM fallback] trying {model}")
                response = await self.nim_client.chat.completions.create(
                    model=model,
                    messages=patched_messages,
                    **nim_kwargs,
                )
                content = response.choices[0].message.content
                logging.info(f"[NIM fallback] succeeded with {model}")
                return [f"nim::{judge}", content]
            except Exception as e:
                logging.warning(f"[NIM fallback] {model} failed: {e}")
                continue

        raise Exception("All NVIDIA NIM models failed. No further fallback available.")

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

        logging.warning("[Groq fallback] All Groq models failed. Escalating to NVIDIA NIM.")
        return await self.nim_fallback_completion(messages, parse_json=parse_json, **kwargs)

    async def make_llm_call(
        self,
        messages: Iterable[ChatCompletionMessageParam],
        model: str,
        stream: bool = False,
        parse_json: bool = True,
        _is_fallback: bool = False,
        **kwargs,
    ) -> Any:
        with self._tracer.start_observation(name="llm_call", observation_type='generation'):
            try:
                call_kwargs = dict(kwargs)
                if parse_json and not stream:
                    call_kwargs.setdefault("response_format", {"type": "json_object"})

                client, clean_model = self._get_client_and_model(model)
                logging.info(f"[LLM] using {clean_model}")
                response = await client.chat.completions.create(
                    messages=list(messages),
                    model=clean_model,
                    stream=stream,
                    **call_kwargs,
                )
            except Exception as e:
                if _is_fallback:
                    raise
                logging.warning(f"[Gemini] {model} failed: {e}. Falling back to Groq.")
                judge, response_content = await self.groq_fallback_completion(
                    messages, parse_json=parse_json, **kwargs
                )
                self._tracer.update_trace(input=messages, output=response_content)
                if parse_json and not stream:
                    return self._extract_json(_FakeCompletion(judge, response_content))
                return _FakeCompletion(judge, response_content)

            self._tracer.update_trace(input=messages, output=response)
            if parse_json and not stream:
                return self._extract_json(response)
            return response

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
            model = self.gemini_models[0]
            judge = f"gemini::{self.gemini_models[1]}"
            try:
                response = await self.make_llm_call(
                    messages=messages, model=model, stream=False, parse_json=parse_json, **kwargs
                )
                return [judge, response]
            except Exception:
                judge, response_content = await self.groq_fallback_completion(
                    messages=messages, parse_json=parse_json, **kwargs
                )
                if response_content:
                    if parse_json:
                        parsed = self._extract_json(_FakeCompletion(judge, response_content))
                        return [judge, parsed]
                    return [judge, response_content]
            raise Exception("All model attempts failed.")

    async def call_llm_streamed(
        self, model: str, messages: Iterable[ChatCompletionMessageParam], **kwargs
    ) -> Any:
        return await self.make_llm_call(model=model, messages=messages, stream=True, **kwargs)

    async def streamed_response(
        self, judge: str, messages: Iterable[ChatCompletionMessageParam], **kwargs
    ) -> AsyncGenerator[str, None]:
        async with self._sem:
            try:
                clean_kwargs = {k: v for k, v in kwargs.items() if k != "response_format"}
                client, clean_model = self._get_client_and_model(judge)
                stream = await client.chat.completions.create(
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
                logging.warning(f"[Streamed] Model attempt failed: {e}")
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