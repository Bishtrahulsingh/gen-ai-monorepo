from fastapi import Request
from fastapi.exceptions import RequestValidationError
from logging import getLogger
from fastapi import status
from starlette.responses import JSONResponse

logger = getLogger(__name__)


async def validation_error(request:Request, exc:RequestValidationError):
    logger.error(f'validation error: {exc.errors()}')
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            'success':False,
            'message':'validation error',
            'detail': exc.errors()
        }
    )


async def exception_handler(request:Request, exc:Exception):
    logger.error(f'exception handler: {exc}')
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            'success':False,
            'message':'something went wrong',
            'detail': str(exc)
        }
    )



