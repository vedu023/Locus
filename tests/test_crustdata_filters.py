import pytest
from pydantic import ValidationError

from app.core.errors import AppError
from app.crustdata.filters import (
    FilterCondition,
    FilterGroup,
    filter_to_payload,
    to_safe_contains_pattern,
)


def test_safe_contains_pattern_escapes_regex_input():
    pattern = to_safe_contains_pattern(["VP Sales", "C++"])
    assert pattern == r"VP\ Sales|C\+\+"


def test_safe_contains_pattern_rejects_empty_input():
    with pytest.raises(AppError):
        to_safe_contains_pattern(["", "   "])


def test_filter_condition_rejects_missing_required_value():
    with pytest.raises(ValidationError):
        FilterCondition(field="headcount.total", type="=>")


def test_filter_group_serializes_recursively():
    group = FilterGroup(
        op="and",
        conditions=[
            FilterCondition(field="headcount.total", type="=>", value=50),
            FilterGroup(
                op="or",
                conditions=[
                    FilterCondition(field="locations.hq_country", type="in", value=["IND"]),
                    FilterCondition(field="locations.hq_country", type="in", value=["SGP"]),
                ],
            ),
        ],
    )

    assert filter_to_payload(group) == {
        "op": "and",
        "conditions": [
            {"field": "headcount.total", "type": "=>", "value": 50},
            {
                "op": "or",
                "conditions": [
                    {"field": "locations.hq_country", "type": "in", "value": ["IND"]},
                    {"field": "locations.hq_country", "type": "in", "value": ["SGP"]},
                ],
            },
        ],
    }
