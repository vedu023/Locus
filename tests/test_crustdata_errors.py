from app.crustdata.errors import normalize_crustdata_error


def test_normalize_crustdata_error_maps_status_codes():
    assert normalize_crustdata_error(400, {}, "/company/search").code == "CRUSTDATA_BAD_REQUEST"
    assert normalize_crustdata_error(401, {}, "/company/search").code == "CRUSTDATA_AUTH_FAILED"
    assert normalize_crustdata_error(403, {}, "/company/search").code == "CRUSTDATA_FORBIDDEN"
    assert normalize_crustdata_error(429, {}, "/company/search").code == "CRUSTDATA_RATE_LIMITED"
    assert normalize_crustdata_error(500, {}, "/company/search").code == "CRUSTDATA_SERVER_ERROR"
