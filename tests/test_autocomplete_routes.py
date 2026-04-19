from app.api.routes import autocomplete as autocomplete_routes
from app.crustdata.types import AutocompleteResponse, AutocompleteSuggestion


def test_company_autocomplete_route(client, monkeypatch):
    monkeypatch.setattr(
        autocomplete_routes,
        "company_autocomplete",
        lambda _client, _request: AutocompleteResponse(
            suggestions=[AutocompleteSuggestion(value="Acme")]
        ),
    )

    response = client.post(
        "/api/autocomplete/company",
        json={"field": "basic_info.name", "query": "acme", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json() == {"suggestions": [{"value": "Acme"}]}


def test_person_autocomplete_route(client, monkeypatch):
    monkeypatch.setattr(
        autocomplete_routes,
        "person_autocomplete",
        lambda _client, _request: AutocompleteResponse(
            suggestions=[AutocompleteSuggestion(value="VP Sales")]
        ),
    )

    response = client.post(
        "/api/autocomplete/person",
        json={"field": "experience.employment_details.current.title", "query": "vp", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json() == {"suggestions": [{"value": "VP Sales"}]}
