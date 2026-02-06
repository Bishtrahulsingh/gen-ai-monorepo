from packages.core.core.app import create_app
from apps.p1_diligence_analyst.app.router import company_router
from apps.p1_diligence_analyst.app.router import document_router

app = create_app()
app.include_router(company_router,tags=["Company routes"])
app.include_router(document_router,tags=['Document routes'])

@app.get('/')
async def root():
    return {'message':'welcome to our website'}

