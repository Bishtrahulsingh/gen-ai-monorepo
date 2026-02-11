from diligence_core.app import create_app
from diligence_core.llm import LLMWrapper
from .prompts.p1_memo.load_prompt import load_prompt
from .routers import company_router,document_router
app = create_app()
app.include_router(company_router,tags=["Company routes"])
app.include_router(document_router,tags=['Document routes'])


@app.get('/')
async def test_something():
    print(load_prompt("apps/p1_diligence_analyst/diligence_analyst/prompts/p1_memo/system.md"))


@app.get('/health')
async def root():
    return {'message':'app is working'}

