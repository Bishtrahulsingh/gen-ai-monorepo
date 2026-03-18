import json
import uuid
from fastapi import APIRouter
from langfuse import observe, get_client
from starlette.responses import StreamingResponse
from diligence_analyst.prompts.p1_memo.load_prompt import replace_input_values, load_prompt, chunk_to_str
from diligence_analyst.schemas.retrivalschema import RetrivalSchema
from diligence_core.llm import LLMWrapper
from diligence_core.reranker.commonreranker import async_reranker

def sse(event: str, data: dict) -> str:
    return f'event:{event}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n'

router = APIRouter(prefix='/api/result')

@router.post('/stream')
@observe(name="analyze_query")
async def llm_calling(payload: RetrivalSchema):
    lf = get_client()
    llm = LLMWrapper()
    user_query = payload.query
    company_name = payload.company_name

    context = await llm.hyde_based_context_retrival(
        query=user_query,
        company_id=payload.company_id,
        collection_name=payload.collection_name
    )

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

    request_id = str(uuid.uuid4())
    judge, raw_response = await llm.non_streamed_response(messages=generator_messages)
    judge_system_prompt = load_prompt('system_template_judge.md')

    evaluator_messages = [
        {'role': 'system', 'content': judge_system_prompt},
        {'role': 'user', 'content': (
            f"Question: {user_query}\n\n"
            f"Retrieved context:\n{chunk_to_str(top_k_chunks)}\n\n"
            f"Generated answer:\n{raw_response}"
        )}
    ]

    judge_evaluation = await llm.make_llm_call(
        messages=evaluator_messages, model=judge, stream=False
    )

    try:
        scores = json.loads(judge_evaluation.choices[0].message.content)
        trace_id = lf.get_current_trace_id()
        for name, value in scores.items():
            if isinstance(value, (int, float)) and trace_id:
                lf.create_score(
                    trace_id=trace_id,
                    name=name,
                    value=float(value)
                )
    except (json.JSONDecodeError, KeyError, AttributeError):
        pass

    lf.update_current_trace(
        input=user_query,
        metadata={
            "company": company_name,
            "chunks_retrieved": len(top_k_chunks),
        }
    )
    lf.flush()

    async def stream_chunk():
        try:
            yield sse('status', {'request_id': request_id, 'state': 'start'})
            chunk_size = 50
            for i in range(0, len(raw_response), chunk_size):
                yield sse('delta', {'request_id': request_id, 'text': raw_response[i:i + chunk_size]})
            judge_content = judge_evaluation.choices[0].message.content
            yield sse('judge', {'request_id': request_id, 'evaluation': judge_content})
            yield sse('status', {'request_id': request_id, 'state': 'complete'})
        except Exception as e:
            yield sse('error', {'request_id': request_id, 'error': str(e), 'message': 'STREAMING FAILED'})
            raise

    return StreamingResponse(stream_chunk(), media_type="text/event-stream")