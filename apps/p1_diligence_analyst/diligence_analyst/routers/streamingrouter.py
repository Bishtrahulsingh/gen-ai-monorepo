import json
from fastapi import APIRouter, Depends, HTTPException
from diligence_analyst.prompts.p1_memo.load_prompt import replace_input_values, load_prompt, chunk_to_str
from diligence_analyst.schemas.retrivalschema import RetrivalSchema
from diligence_core.eval_system.observability.tracer import Tracer
from diligence_core.llm import LLMWrapper
from diligence_core.middlewares.authmiddleware import verify_jwt_token
from diligence_core.reranker.commonreranker import async_reranker

def sse(event: str, data: dict) -> str:
    return f'event:{event}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n'

router = APIRouter(prefix='/api/result')

@router.post('/stream')
async def llm_calling(payload: RetrivalSchema,userdata=Depends(verify_jwt_token)):
    user = userdata['user']
    token = userdata['access_token']

    if not user:
        raise HTTPException(status_code=401, detail="User does not exist")

    tracer = Tracer()
    llm = LLMWrapper()
    user_query = payload.query
    company_name = payload.company_name

    with tracer.start_observation("analyze_query","span"):
        context = await llm.hyde_based_context_retrival(
            query=user_query,
            collection_name=payload.collection_name,
            token=token,
            ticker=payload.ticker,
            fiscal_year=payload.fiscal_year,
        )
        score = context.points[0].score if (context and context.points) else 0
        # tracer.check_retrival_failure(user_query,score)

        top_k_chunks = await async_reranker(context, user_query, top_k=5)
        user_prompt = replace_input_values(
            load_prompt('input_template.md'),
            company_name,
            chunk_to_str(top_k_chunks),
            user_query
        )
        system_prompt = load_prompt('system_template_model1.md')
        generator_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        judge, raw_response = await llm.non_streamed_response(messages=generator_messages)
        judge1_system_prompt = load_prompt('system_template_judge1.md')

        judge1_messages = [
            {'role': 'system', 'content': judge1_system_prompt},
            {'role': 'user', 'content': (
                f"Question: {user_query}\n\n"
                f"Retrieved context:\n{chunk_to_str(top_k_chunks)}\n\n"
                f"Generated answer:\n{raw_response}"
            )}
        ]

        judge_evaluation = await llm.make_llm_call(
            messages=judge1_messages, model=judge, stream=False
        )

        polished_answer = judge_evaluation.get("polished_answer", raw_response)

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

    tracer.flush()

    return {"response":judge_evaluation}
