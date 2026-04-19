from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from app.db.models import SearchRun
from app.lenses.investor import InvestorRunInput
from app.lenses.recruiting import RecruitingRunInput
from app.lenses.sales import SalesRunInput


class CreateRunRequest(BaseModel):
    lens: Literal["sales", "recruiting", "investor"]
    title: str | None = None
    input: SalesRunInput | RecruitingRunInput | InvestorRunInput

    @model_validator(mode="before")
    @classmethod
    def coerce_input_for_lens(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        lens = data.get("lens")
        raw_input = data.get("input")
        if lens is None or raw_input is None:
            return data

        input_models = {
            "sales": SalesRunInput,
            "recruiting": RecruitingRunInput,
            "investor": InvestorRunInput,
        }
        model = input_models.get(lens)
        if model is None:
            return data

        coerced = dict(data)
        coerced["input"] = model.model_validate(raw_input)
        return coerced


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
