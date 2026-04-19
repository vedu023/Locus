from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.crustdata.types import CompanySearchRequest, PersonSearchRequest
from app.db.models import SearchRun


class SalesRunInput(BaseModel):
    search: CompanySearchRequest


class RecruitingRunInput(BaseModel):
    search: PersonSearchRequest


class InvestorRunInput(BaseModel):
    search: CompanySearchRequest


class CreateRunRequest(BaseModel):
    lens: Literal["sales", "recruiting", "investor"]
    title: str | None = None
    input: SalesRunInput | RecruitingRunInput | InvestorRunInput


class CreateRunResponse(BaseModel):
    run_id: str
    status: str
    lens: str
    result_counts: dict[str, Any]

    @classmethod
    def from_search_run(cls, run: SearchRun) -> "CreateRunResponse":
        return cls(
            run_id=run.id,
            status=run.status,
            lens=run.lens,
            result_counts=run.result_counts,
        )


class SearchRunResponse(BaseModel):
    run_id: str
    user_id: str
    lens: str
    title: str | None
    status: str
    input: dict[str, Any]
    normalized_filters: dict[str, Any]
    result_counts: dict[str, Any]
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_search_run(cls, run: SearchRun) -> "SearchRunResponse":
        return cls(
            run_id=run.id,
            user_id=run.user_id,
            lens=run.lens,
            title=run.title,
            status=run.status,
            input=run.input_payload,
            normalized_filters=run.normalized_filters,
            result_counts=run.result_counts,
            error_message=run.error_message,
            created_at=run.created_at,
            completed_at=run.completed_at,
        )
