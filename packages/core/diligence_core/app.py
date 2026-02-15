from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from .exception.globalexception import validation_error,exception_handler
from .middlewares.logging import RequestTracingMiddleware
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

def create_app():
    app_c = FastAPI()
    app_c.add_middleware(RequestTracingMiddleware)
    app_c.add_exception_handler(RequestValidationError,validation_error)
    app_c.add_exception_handler(Exception, exception_handler)
    return app_c

app = create_app()

@app.get('/health')
def health():
    return {'status': 'ok'}