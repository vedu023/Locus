import pytest

from app.core.errors import AppError
from app.crustdata.fields import SALES_COMPANY_FIELDS, get_lens_fields


def test_get_lens_fields_returns_expected_preset():
    fields = get_lens_fields("sales", "company")
    assert fields == SALES_COMPANY_FIELDS
    assert "locations.hq_country" in fields


def test_get_lens_fields_rejects_unknown_keys():
    with pytest.raises(AppError):
        get_lens_fields("unknown", "company")
