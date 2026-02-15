from diligence_core.app import create_app
from .routers import company_router,document_router,streaming_router
app = create_app()
app.include_router(company_router,tags=["Company routes"])
app.include_router(document_router,tags=['Document routes'])
app.include_router(streaming_router,tags=['Streaming routes'])

@app.get('/')
async  def root():
    return {'message':'welcome to our application'}

@app.get('/health')
async def root():
    return {'message':'app is working'}

