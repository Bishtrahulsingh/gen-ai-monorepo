from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from diligence_core import settings

load_dotenv()

from diligence_core.app import create_app
from .routers import company_router,document_router,streaming_router,userauth_router

app = create_app()
app.include_router(company_router,tags=["Company routes"])
app.include_router(document_router,tags=['Document routes'])
app.include_router(streaming_router,tags=['Streaming routes'])
app.include_router(userauth_router,tags=['User routes'])


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
async  def root():
    return {'message':'welcome to our application'}

@app.get('/health')
async def root():
    return {'message':'app is working'}

