from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from .exception.globalexception import validation_error,exception_handler
from .middlewares.logging import RequestTracingMiddleware
import logging

from .supabaseconfig.supabaseconfig import init_supabase
from .vectordb.qdrantConfig import create_collection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app:FastAPI):
    await init_supabase()
    await create_collection('sec_filings', 384)
    yield

def create_app():
    app_c = FastAPI(lifespan=lifespan)
    app_c.add_middleware(RequestTracingMiddleware)
    app_c.add_exception_handler(RequestValidationError,validation_error)
    app_c.add_exception_handler(Exception, exception_handler)
    return app_c

app = create_app()

@app.get('/health')
def health():
    return {'status': 'ok'}