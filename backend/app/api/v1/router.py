"""
Aggregates all v1 routers.
"""
from fastapi import APIRouter

from app.api.v1 import auth, billing, follow_ups, leads, workspaces

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(leads.router, prefix="/workspaces/{workspace_id}/leads", tags=["leads"])
# follow_ups.router and billing.router define their own full paths — no shared prefix.
api_router.include_router(follow_ups.router)
api_router.include_router(billing.router)
