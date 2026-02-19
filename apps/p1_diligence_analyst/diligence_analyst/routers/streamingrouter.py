import json
import uuid
from fastapi import APIRouter
from starlette.responses import StreamingResponse
from diligence_analyst.prompts.p1_memo.load_prompt import replace_input_values, load_prompt, chunk_to_str
from diligence_core.llm import LLMWrapper

def sse(event:str, data:dict)->str:
    return f'event:{event}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n'

router = APIRouter(prefix='/api/result')
@router.post('/stream')
async def llm_calling():
    user_query = "Evaluate the financial health and key risks of FinEdge Analytics"
    company_name= "FinEdge Analytics Pvt Ltd"
    context = [
        "FinEdge Analytics reported a 22% year-over-year revenue growth in FY2024, driven primarily by enterprise SaaS subscriptions.",

        "Approximately 65% of the company’s revenue comes from its top 3 clients, indicating high customer concentration.",

        "The company increased its marketing and sales expenditure by 40% in the last year to drive customer acquisition.",

        "Operating margins declined from 18% to 9% over the past 12 months due to increased spending.",

        "FinEdge Analytics has raised $10M in Series A funding but has not yet achieved profitability.",

        "The company operates in the financial analytics space, providing AI-driven insights to mid-sized financial institutions.",

        "There is no publicly available data on customer churn or retention rates.",

        "The company expanded into two new international markets in the last year, increasing operational complexity.",

        "Cash reserves are expected to sustain operations for approximately 12–15 months at the current burn rate.",

        "Recent hiring trends indicate a 30% increase in engineering headcount, suggesting product expansion efforts."
    ]

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
