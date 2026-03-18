import json
import uuid
from fastapi import APIRouter
from pydantic import Json
from starlette.responses import StreamingResponse
from diligence_analyst.prompts.p1_memo.load_prompt import replace_input_values, load_prompt, chunk_to_str
from diligence_analyst.schemas.retrivalschema import RetrivalSchema
from diligence_core.llm import LLMWrapper
from diligence_core.reranker.commonreranker import async_reranker


def sse(event:str, data:dict)->str:
    return f'event:{event}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n'

router = APIRouter(prefix='/api/result')
@router.post('/stream')
async def llm_calling(payload:RetrivalSchema):
    llm = LLMWrapper()
    user_query = payload.query
    company_name= payload.company_name
    context = await llm.hyde_based_context_retrival(query=user_query, company_id=payload.company_id,collection_name=payload.collection_name)
    #perform reranking here to get top n relevant chunks
    top_k_chunks = await  async_reranker(context, user_query, top_k=5)

    user_prompt = replace_input_values(load_prompt('input_template.md'),company_name,chunk_to_str(top_k_chunks),user_query)
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
    judge_evaluation = await  llm.make_llm_call(messages=evaluator_messages,model=judge,stream=False)
    print("judge response: \n",judge_evaluation.choices[0].message.content,end="\n\n")

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
