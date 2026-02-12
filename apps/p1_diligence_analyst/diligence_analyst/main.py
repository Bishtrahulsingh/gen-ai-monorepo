import json
import uuid

from starlette.responses import StreamingResponse

from diligence_core.app import create_app
from diligence_core.llm import LLMWrapper
from .prompts.p1_memo.load_prompt import load_prompt
from .routers import company_router,document_router
app = create_app()
app.include_router(company_router,tags=["Company routes"])
app.include_router(document_router,tags=['Document routes'])


def sse(event:str, data:dict)->str:
    return f'event:{event}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n'

@app.get('/stream')
async def test_something():
    user_query = "What is 2+2 give one line ans."
    system_prompt = "You are a HELPFUL Assistant."
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]
    llm= LLMWrapper()

    request_id = str(uuid.uuid4())

    async def stream_chunk():
        try:
            yield sse('status',{'request_id': request_id, 'state':'start'})
            async for chunk in llm.streamed_response(messages=messages):
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
    return StreamingResponse(stream_chunk(), media_type="text/event-stream")


@app.get('/health')
async def root():
    return {'message':'app is working'}

