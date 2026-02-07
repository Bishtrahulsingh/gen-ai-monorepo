from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from packages.core.core.exception.globalexception import validation_error, exception_handler
from packages.core.core.middlewares.logging import RequestTracingMiddleware


def create_app():
    app = FastAPI()
    app.add_middleware(RequestTracingMiddleware)
    app.add_exception_handler(RequestValidationError,validation_error)
    app.add_exception_handler(Exception, exception_handler)
    return app

app = create_app()

@app.get('/health')
def health():
    return {'status': 'ok'}