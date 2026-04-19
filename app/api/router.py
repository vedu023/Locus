from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.autocomplete import router as autocomplete_router
from app.api.routes.health import router as health_router
from app.api.routes.investor import router as investor_router
from app.api.routes.map import router as map_router
from app.api.routes.recruiting import router as recruiting_router
from app.api.routes.runs import router as runs_router
from app.api.routes.sales import router as sales_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router, prefix="/api")
api_router.include_router(autocomplete_router, prefix="/api")
api_router.include_router(runs_router, prefix="/api")
api_router.include_router(map_router, prefix="/api")
api_router.include_router(investor_router, prefix="/api")
api_router.include_router(recruiting_router, prefix="/api")
api_router.include_router(sales_router, prefix="/api")
