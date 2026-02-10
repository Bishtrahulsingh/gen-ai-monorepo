from diligence_core.app import create_app
from .llm.llmwrapper import LLMWrapper
from .routers import company_router,document_router
app = create_app()
app.include_router(company_router,tags=["Company routes"])
app.include_router(document_router,tags=['Document routes'])


@app.get('/')
async def test_something():
    user_query = "Who is bill gates?In 5 words"
    system_prompt = "You are a HELPFUL Assistant."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    llm = LLMWrapper()
    await llm.complete(messages=messages)


@app.get('/health')
async def root():
    return {'message':'app is working'}

