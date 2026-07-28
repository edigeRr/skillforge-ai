from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import new_request_id, request_id_ctx


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = new_request_id()
        token = request_id_ctx.set(req_id)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = req_id
        return response
