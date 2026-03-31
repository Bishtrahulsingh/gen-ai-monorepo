import asyncio
import enum
import json
import logging
import re
import uuid
from typing import Iterable, AsyncGenerator, Any, List, Optional, Union
from groq import AsyncGroq, AsyncStream
from groq.types.chat import ChatCompletionMessageParam, ChatCompletion, ChatCompletionChunk
from starlette.responses import JSONResponse

from diligence_core import settings
from diligence_core.eval_system.observability.tracer import Tracer
from diligence_core.supabaseconfig import supabaseconfig
from diligence_core.vectordb.qdrantConfig import filter_and_search_chunks


class LLMWrapper:
    def __init__(self,max_allowed:int=10):
        self.models=['llama-3.1-8b-instant','llama-3.3-70b-versatile','openai/gpt-oss-20b','openai/gpt-oss-120b']
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self._sem = asyncio.Semaphore(max_allowed)
        self._tracer = Tracer()

    async def hyde_based_context_retrival(self,query: str, collection_name: str,token:str,ticker:str, fiscal_year:int):
        #make a llm call for an example ans possible for best retrival
        supabase_client = supabaseconfig.supabase_client
        with self._tracer.start_observation(name="hyde retrival",observation_type="span"):
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

            if res.data:
                keywords = res.data[0]["keywords"]
                print(keywords)

            query_messages = [
                {
                    "role": "system",
                    "content": f"""You are a retrieval query synthesizer for SEC 10-K filings.

            Your sole function is to generate a hypothetical document passage for semantic retrieval.
            You are not answering the user's question. You are writing text that would plausibly
            appear in the relevant section of a 10-K, so that a vector search against real filings
            returns the most relevant chunks.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            PHASE 1 — INTENT MAPPING
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Before writing, identify:

            1. PRIMARY SECTION — which 10-K section is most likely to contain the answer?
               Pick the single best match from the available keywords:
               {keywords}

               If no keyword matches, infer the closest section from the query's subject matter.

            2. SECONDARY SECTIONS — up to two additional sections that commonly co-occur
               with the primary section for this query type. Use only if they would materially
               improve retrieval. If none apply, use none.

            3. LINGUISTIC REGISTER — the dominant language style of the target section:
               NARRATIVE    → business, strategy, competition, operations
               RISK-LEGAL   → risk_factors, regulatory_environment, legal_proceedings
               MD&A         → management_discussion, financial_overview, liquidity

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            PHASE 2 — PASSAGE GENERATION
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Write a single hypothetical passage of 4–6 sentences.

            REQUIRED:
              □ Formal SEC filing prose — match the linguistic register identified in Phase 1.
              □ Conceptually expand the query using the primary and secondary sections.
              □ Use terminology and sentence structures that appear in real 10-K filings.
              □ Mirror the density and hedging style of the target section
                (risk sections hedge with "may," "could," "there can be no assurance";
                 MD&A uses "compared to the prior period," "reflects," "was primarily driven by";
                 narrative sections use "the Company believes," "intends to," "has positioned").

            PROHIBITED:
              □ No numerical values — no revenue figures, percentages, growth rates, or metrics.
                 Use only ordinal or qualitative language: "increased," "declined materially,"
                 "remained consistent," "was adversely affected."
              □ No fabricated facts — no named products, named competitors, specific geographies,
                 or events not present in the query.
              □ No direct restatement of the user's question.
              □ No first-person voice ("I," "we" at the synthesizer level — the passage itself
                 may use "the Company" or "management" as 10-Ks do).
              □ No commentary, preamble, or explanation outside the passage itself.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            OUTPUT
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            Return only the passage. No labels, no JSON, no section headers, no explanation.
            The passage is the entire output."""
                },
                {
                    "role": "user",
                    "content": query
                },
            ]

            response = await self.client.chat.completions.create(
                messages=query_messages,
                model='llama-3.1-8b-instant'
            )

            content = response.choices[0].message.content

            context = await filter_and_search_chunks(collection_name=collection_name, query=content,ticker=ticker, fiscal_year=fiscal_year)
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
                print(f"\nusing {available_model} for this call\n")
                response = await self.make_llm_call(
                messages=messages,
                model=available_model,
                stream=False,
                **kwargs
                )

                return [judge,response.choices[0].message.content]
            except Exception as e:
                continue
        raise Exception(f'Model not available currently ')

    async def make_llm_call(self,messages:Iterable[ChatCompletionMessageParam],model:str,stream:bool=False,parse_json:bool=True,**kwargs)-> Union[ChatCompletion | AsyncStream[ChatCompletionChunk] | JSONResponse]:
        with self._tracer.start_observation(name="llm_call", observation_type='generation'):
            try:
                if parse_json and not stream:
                    kwargs.setdefault("response_format", {"type": "json_object"})


                print(f"\nusing {model} for this call\n")
                response = await self.client.chat.completions.create(
                    messages=messages,
                    model=model,
                    stream=stream,
                    **kwargs
                )
            except Exception:
                judge,response = await self.fallback_completion(messages,model)

            self._tracer.update_trace(
                input=messages,
                output=response,
            )
            if parse_json and not stream:
                return self._extract_json(response)

            return response

    def _extract_json(self, response: ChatCompletion) -> Any:
        raw = response.choices[0].message.content or ""

        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.DOTALL)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*}|\[.*])", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"Could not extract JSON from response: {raw!r}")

    async def non_streamed_response(self,messages:Iterable[ChatCompletionMessageParam],**kwargs):
        async with self._sem:
            model = self.models[0]
            judge = self.models[1]
            try:
                response = await  self.make_llm_call(messages=messages ,model=model,stream=False,**kwargs)
                return [judge,response]
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