from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.health import build_readiness_report

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "locus-api"}


@router.get("/ready")
def ready() -> JSONResponse:
    payload, status_code = build_readiness_report()
    return JSONResponse(status_code=status_code, content=payload)
