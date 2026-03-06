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
    user_query = "what is the summary?"
    company_name= "FinEdge Analytics Pvt Ltd"
    context = [
    "The startup launched its product in January with an initial user base of 500 customers.",
    "By March, the number of active users had grown to around 2000.",
    "In April, the company introduced a premium subscription priced at $10 per month.",
    "Only about 5% of the users converted to the paid plan in the first month.",
    "Customer acquisition cost (CAC) is estimated to be around $8 per user.",
    "The average revenue per paying user (ARPU) is approximately $10.",
    "In May, the startup spent heavily on marketing, increasing total users to 5000.",
    "However, the conversion rate dropped slightly to 4% after the marketing campaign.",
    "The team noticed that users acquired through organic channels had higher retention than paid ads.",
    "Monthly churn rate for paid users is around 10%.",
    "The startup currently has a team of 8 people, including 3 engineers and 2 marketing specialists.",
    "Infrastructure costs have been increasing as more users join the platform.",
    "The company is planning to raise a seed round in the next 3 months.",
    "Investors are particularly interested in growth rate and retention metrics.",
    "The founders believe improving product quality will increase conversion rates."
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
