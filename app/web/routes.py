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


# How to verify the members-only pages
# ====================================
#
# /interview, /history and /dashboard load static/js/guard.js in <head>. Without an access
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
