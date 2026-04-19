from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.core.errors import AppError

Operator = Literal[
    "=",
    "!=",
    ">",
    "<",
    "=>",
    "=<",
    "in",
    "not_in",
    "(.)",
    "[.]",
    "is_null",
    "is_not_null",
    "geo_distance",
]


class FilterCondition(BaseModel):
    field: str
    type: Operator
    value: object | None = None

    @model_validator(mode="after")
    def validate_operator_rules(self) -> "FilterCondition":
        if self.type in {"is_null", "is_not_null"} and self.value is not None:
            raise ValueError(f"Operator {self.type} does not accept a value.")
        if self.type not in {"is_null", "is_not_null"} and self.value is None:
            raise ValueError(f"Operator {self.type} requires a value.")
        return self


class FilterGroup(BaseModel):
    op: Literal["and", "or"]
    conditions: list["FilterNode"]


FilterNode = Annotated[FilterCondition | FilterGroup, Field(discriminator=None)]
FilterGroup.model_rebuild()


def escape_regex(value: str) -> str:
    return re.escape(value.strip())


def to_safe_contains_pattern(values: list[str]) -> str:
    cleaned_values = [escape_regex(value) for value in values if value.strip()]
    if not cleaned_values:
        raise AppError(
            code="BAD_INPUT",
            message="At least one non-empty filter value is required.",
            status_code=400,
        )
    return "|".join(cleaned_values)


def filter_to_payload(node: FilterCondition | FilterGroup) -> dict:
    if isinstance(node, FilterCondition):
        return node.model_dump(exclude_none=True)
    return {
        "op": node.op,
        "conditions": [filter_to_payload(condition) for condition in node.conditions],
    }
