from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, unhandled_exception_handler
from app.core.logging import configure_logging
from app.ui.routes import get_ui_assets_dir
from app.ui.routes import router as ui_router

logger = logging.getLogger("locus.http")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
    )

    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)
    application.mount("/ui", StaticFiles(directory=str(get_ui_assets_dir())), name="ui")
    application.include_router(ui_router)
    application.include_router(api_router)

    @application.middleware("http")
    async def request_context_middleware(request: Request, call_next) -> JSONResponse:
        request_id = uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request.failed",
                extra={
                    "event": "request.failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            raise

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request.completed",
            extra={
                "event": "request.completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return response

    return application


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
