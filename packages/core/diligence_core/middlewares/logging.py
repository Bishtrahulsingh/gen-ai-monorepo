from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
import time
import logging
logger = logging.getLogger(__name__)

class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
            self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()

        user_id = request.headers.get("X-Request-Id", "anonymous")
        endpoint = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = user_id
            return response
        except Exception as e:
            status_code = 500
            logger.exception(
                f"user={user_id} ip={client_ip} "
                f"method={method} endpoint={endpoint} "
                f"status={status_code} error={str(e)}"
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000

            logger.info(
                f"user={user_id} ip={client_ip} "
                f"method={method} endpoint={endpoint} "
                f"status={status_code} duration_ms={duration_ms:.2f}"
            )
