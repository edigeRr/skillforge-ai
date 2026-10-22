"""Page routes for the browser frontend. These serve plain static HTML -
all dynamic behavior happens client-side via static/js/*.js calling the
existing JSON API. Kept out of the OpenAPI schema since these aren't API
endpoints.
"""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

router = APIRouter(include_in_schema=False)

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


def _page(filename: str) -> FileResponse:
    return FileResponse(STATIC_DIR / filename)


def _wants_a_page(request: Request) -> bool:
    path = request.url.path
    accepts_html = "text/html" in request.headers.get("accept", "")
    return accepts_html and not path.startswith(("/api/", "/static/"))


async def not_found_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """Browsers get the 404 page for unknown addresses; API clients and
    missing static files keep FastAPI's usual JSON 404."""
    if exc.status_code == 404 and _wants_a_page(request):
        return FileResponse(STATIC_DIR / "404.html", status_code=404)
    return await http_exception_handler(request, exc)


@router.get("/")
async def home() -> FileResponse:
    return _page("index.html")


@router.get("/register")
async def register_page() -> FileResponse:
    return _page("register.html")


@router.get("/login")
async def login_page() -> FileResponse:
    return _page("login.html")


# How to verify the members-only pages
# ====================================
#
# /interview, /history, /dashboard and /admin load static/js/guard.js in <head>. Without an access
# token in the browser it replaces the page with /login before anything is shown. The guard
# is a convenience, not security: the data behind these pages comes from API endpoints that
# check the token themselves.
#
# 1. In the browser
#      docker compose up --build
#    Open http://localhost:8000/dashboard in a private window.
#    Expected: the address bar shows /login, and the Back button does not return to /dashboard.
#    Log in, then open /interview, /history and /dashboard.
#    Expected: each page stays open and the nav shows Dashboard / Interview / Log out.
#    Press "Log out" and open /history again. Expected: back on /login.
#
# 2. Automated tests (same test database as in the registration block in app/api/v1/auth.py)
#      pytest tests/integration/test_pages.py -q
#      cd tests-frontend
#      npm test


@router.get("/interview")
async def interview_page() -> FileResponse:
    return _page("interview.html")


@router.get("/history")
async def history_page() -> FileResponse:
    return _page("history.html")


@router.get("/dashboard")
async def dashboard_page() -> FileResponse:
    return _page("dashboard.html")


@router.get("/admin")
async def admin_page() -> FileResponse:
    return _page("admin.html")


@router.get("/interview/{interview_id}")
async def interview_session_page(interview_id: UUID) -> FileResponse:
    return _page("session.html")
