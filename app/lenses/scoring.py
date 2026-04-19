from __future__ import annotations

from datetime import date


def clamp(value: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def weighted_average(scores: dict[str, tuple[float, float]]) -> float:
    total_weight = sum(weight for _value, weight in scores.values() if weight > 0)
    if total_weight <= 0:
        return 0.0

    weighted_sum = sum(value * weight for value, weight in scores.values() if weight > 0)
    return weighted_sum / total_weight


def employee_fit(employee_count: int | None) -> float:
    if employee_count is None:
        return 0.35
    if 50 <= employee_count <= 500:
        return 1.0
    if 20 <= employee_count <= 1500:
        return 0.8
    if 10 <= employee_count <= 5000:
        return 0.55
    return 0.2


def funding_fit(total_funding_usd: float | None, last_round_amount_usd: float | None) -> float:
    funding_signal = max(total_funding_usd or 0.0, last_round_amount_usd or 0.0)
    if funding_signal >= 50_000_000:
        return 1.0
    if funding_signal >= 10_000_000:
        return 0.85
    if funding_signal >= 1_000_000:
        return 0.65
    if funding_signal > 0:
        return 0.45
    return 0.2


def funding_recency_fit(last_funding_date: date | None, *, today: date | None = None) -> float:
    if last_funding_date is None:
        return 0.35

    reference = today or date.today()
    age_days = (reference - last_funding_date).days
    if age_days <= 365:
        return 1.0
    if age_days <= 730:
        return 0.8
    if age_days <= 1460:
        return 0.55
    return 0.25


def buyer_coverage_fit(buyer_count: int, target_buyers: int) -> float:
    if target_buyers <= 0:
        return 0.0
    return clamp(buyer_count / target_buyers)
