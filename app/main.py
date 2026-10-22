from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import health
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppException, app_exception_handler
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.web.routes import not_found_handler
from app.web.routes import router as web_router

settings = get_settings()
configure_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "AI-powered mock technical interview platform. Register, log in with "
        "the **Authorize** button above, start an interview, and answer "
        "questions right from this page - no separate frontend needed. "
        "Full docs: https://github.com/edigeRr/skillforge-ai"
    ),
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(StarletteHTTPException, not_found_handler)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(health.router)
app.include_router(api_router)
app.include_router(web_router)
