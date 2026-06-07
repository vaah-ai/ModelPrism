"""API route handlers package.

Route modules are imported and included in ``api_router`` below.
"""

from fastapi import APIRouter

api_router = APIRouter()

from app.api.agents import router as agents_router  # noqa: E402

api_router.include_router(agents_router)
