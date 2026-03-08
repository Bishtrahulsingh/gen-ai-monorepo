import json
import logging
import uuid
from fastapi import APIRouter
from starlette.responses import StreamingResponse
from diligence_analyst.prompts.p1_memo.load_prompt import replace_input_values, load_prompt, chunk_to_str
from diligence_analyst.schemas.retrivalschema import RetrivalSchema
from diligence_core.llm import LLMWrapper
from diligence_core.vectordb.qdrantConfig import filter_and_search_chunks


def sse(event:str, data:dict)->str:
    return f'event:{event}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n'

router = APIRouter(prefix='/api/result')
@router.post('/stream')
async def llm_calling(payload:RetrivalSchema):
    user_query = payload.query
    company_name= payload.company_name
    context = await filter_and_search_chunks(collection_name=payload.collection_name, query=user_query, company_id=payload.company_id)

    user_prompt = replace_input_values(load_prompt('input_template.md'),company_name,chunk_to_str(context),user_query)
    system_prompt = load_prompt('system_template_model1.md')
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    llm= LLMWrapper()

    request_id = str(uuid.uuid4())
    judge, raw_response = await llm.non_streamed_response(messages=messages)
    judge_system_prompt = load_prompt('system_template_judge.md')
    messages = [
        {'role': 'system', 'content': judge_system_prompt},
        {'role': 'user', 'content': raw_response}
    ]

    async def stream_chunk():
        try:
            yield sse('status',{'request_id': request_id, 'state':'start'})
            async for chunk in llm.streamed_response(judge=judge,messages=messages):
                yield sse('delta',{'request_id':request_id, 'text':chunk})
            yield  sse('status', {'request_id': request_id, 'state':'complete'})
        except Exception as e:
            sse(
                'error',
                {
                    'request_id': request_id,
                    'error': str(e),
                    'message':'STREAMING FAILED'
                }
            )
            raise
    return StreamingResponse(stream_chunk(), media_type="text/event-stream")
