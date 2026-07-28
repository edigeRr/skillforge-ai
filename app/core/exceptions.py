from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base class for application-level errors that map to a clean HTTP response."""

    status_code = 500
    error_code = "INTERNAL_ERROR"

    def __init__(
        self,
        detail: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code
        super().__init__(detail)


class NotFoundError(AppException):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(AppException):
    status_code = 409
    error_code = "CONFLICT"


class UnauthorizedError(AppException):
    status_code = 401
    error_code = "UNAUTHORIZED"


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
    )
