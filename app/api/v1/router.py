from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

# Sprint 2+: include feature routers here as they're built, e.g.
# from app.api.v1 import auth, profile, interview, history, dashboard
# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
