import gc
import json
from fastapi import APIRouter, Depends, HTTPException
from diligence_analyst.prompts.p1_memo.load_prompt import (
    replace_input_values, load_prompt, chunk_to_str, build_chunk_metadata_map
)
from diligence_analyst.schemas.retrivalschema import RetrivalSchema
from diligence_core.eval_system.observability.tracer import Tracer
from diligence_core.middlewares.authmiddleware import verify_jwt_token
from diligence_core.reranker.commonreranker import async_reranker

_llm = None

def _get_llm():
    global _llm
    if _llm is None:
        from diligence_core.llm import LLMWrapper
        _llm = LLMWrapper()
    return _llm


def sse(event: str, data: dict) -> str:
    return f'event:{event}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n'

router = APIRouter(prefix='/api/result')


@router.post('/stream')
async def llm_calling(payload: RetrivalSchema, userdata=Depends(verify_jwt_token)):
    user = userdata['user']
    token = userdata['access_token']

    if not user:
        raise HTTPException(status_code=401, detail="User does not exist")

    tracer = Tracer()
    llm = _get_llm()
    user_query = payload.query
    company_name = payload.company_name

    with tracer.start_observation("analyze_query", "span"):
        context = await llm.hyde_based_context_retrival(
            query=user_query,
            collection_name=payload.collection_name,
            token=token,
            ticker=payload.ticker,
            fiscal_year=payload.fiscal_year,
        )
        score = context.points[0].score if (context and context.points) else 0

        top_k_chunks = await async_reranker(context, user_query, top_k=5)

        del context
        gc.collect()

        chunk_metadata_map = build_chunk_metadata_map(top_k_chunks)

        chunks_str = chunk_to_str(top_k_chunks)

        system_prompt = load_prompt('system_template_model1.md')
        user_prompt = replace_input_values(
            load_prompt('input_template.md'),
            company_name,
            chunks_str,
            user_query,
        )
        generator_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]

        judge, raw_response = await llm.non_streamed_response(
            messages=generator_messages
        )

        del generator_messages, system_prompt, user_prompt
        gc.collect()

        judge1_system_prompt = load_prompt('system_template_judge1.md')
        judge1_messages = [
            {'role': 'system', 'content': judge1_system_prompt},
            {'role': 'user',   'content': (
                f"Question: {user_query}\n\n"
                f"Retrieved context:\n{chunks_str}\n\n"  
                f"Generated answer:\n{raw_response}"
            )},
        ]

        judge_evaluation = await llm.make_llm_call(
            messages=judge1_messages, model=judge, stream=False
        )

        del judge1_messages, judge1_system_prompt, chunks_str, raw_response
        gc.collect()

        score_fields = ("faithfulness", "answer_relevance", "context_precision")
        scores = {k: judge_evaluation[k] for k in score_fields if k in judge_evaluation}
        if scores:
            tracer.score_evaluation(scores)

        tracer.add_tags(
            tags=[judge_evaluation.get("verdict", "unknown")],
            hallucinated_claims=judge_evaluation.get("hallucinated_claims", []),
            issues=judge_evaluation.get("issues", []),
            evidence=judge_evaluation.get("evidence", ""),
        )

        evidence = judge_evaluation.get("evidence", {})
        evidence_meta = {}

        supporting_idx = evidence.get("supporting_chunk_index")
        contradicting_idx = evidence.get("contradicting_chunk_index")

        if supporting_idx is not None and supporting_idx in chunk_metadata_map:
            evidence_meta["supporting"] = chunk_metadata_map[supporting_idx]

        if contradicting_idx is not None and contradicting_idx in chunk_metadata_map:
            evidence_meta["contradicting"] = chunk_metadata_map[contradicting_idx]

    tracer.flush()

    return {
        "response": {
            **judge_evaluation,
            "evidence_meta": evidence_meta,
        }
    }