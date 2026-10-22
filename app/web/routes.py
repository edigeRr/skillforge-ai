"""Page routes for the browser frontend. These serve plain static HTML -
all dynamic behavior happens client-side via static/js/*.js calling the
existing JSON API. Kept out of the OpenAPI schema since these aren't API
endpoints.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(include_in_schema=False)

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


def _page(filename: str) -> FileResponse:
    return FileResponse(STATIC_DIR / filename)


@router.get("/")
async def home() -> FileResponse:
    return _page("index.html")


@router.get("/register")
async def register_page() -> FileResponse:
    return _page("register.html")


@router.get("/login")
async def login_page() -> FileResponse:
    return _page("login.html")


@router.get("/interview")
async def interview_page() -> FileResponse:
    return _page("interview.html")


@router.get("/history")
async def history_page() -> FileResponse:
    return _page("history.html")


@router.get("/dashboard")
async def dashboard_page() -> FileResponse:
    return _page("dashboard.html")
