from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
import time
from logging import Formatter, StreamHandler, getLogger, INFO

# ---- logging setup (console) ----
logger = getLogger("api_timing")
logger.setLevel(INFO)
handler = StreamHandler()
formatter = Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)



class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.time()
        user_id = request.headers.get('X-Request-Id','anonymous')

        response = await call_next(request)

        duration_ms = (time.time() - start)*1000
        endpoint = request.url.path

        client_ip = request.client.host if request.client else "unknown"

        logger.info(
            f"user={user_id} ip={client_ip} "
            f"method={request.method} endpoint={endpoint} "
            f"status={response.status_code} duration_ms={duration_ms:.2f}"
        )

        return response