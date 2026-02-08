from core.app import create_app
from .router import company_router,document_router
app = create_app()
app.include_router(company_router,tags=["Company routes"])
app.include_router(document_router,tags=['Document routes'])

@app.get('/health')
async def root():
    return {'message':'app is working'}

