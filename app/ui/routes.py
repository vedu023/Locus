from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

router = APIRouter(include_in_schema=False)


def get_ui_assets_dir() -> Path:
    return ASSETS_DIR


def _index_file() -> Path:
    return ASSETS_DIR / "index.html"


@router.get("/")
def get_workbench() -> FileResponse:
    return FileResponse(_index_file())


@router.get("/workbench")
def get_workbench_alias() -> FileResponse:
    return FileResponse(_index_file())
