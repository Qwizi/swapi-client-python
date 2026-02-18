#!/usr/bin/env python3
"""Tests for the new _params.py query parameter builder (v3 API)."""

from src.swapi_client._params import build_params


def _show(title: str, params: dict) -> None:
    print(f"=== {title} ===")
    for key, value in sorted(params.items()):
        print(f"  {key} = {value!r}")
    print()


def test_basic_filter():
    params = build_params(filter={"name": "John", "age__gte": 18, "status__isNotNull": ""})
    _show("Basic filter", params)
    assert params["filter[name][eq]"] == "John"
    assert params["filter[age][gte]"] == "18"
    assert params["filter[status][isNotNull]"] == ""


def test_nested_filter():
    params = build_params(filter={
        "attributes.476__hasText": "some text",       # numeric segment → multiple brackets
        "commissionPhase.commissionPhaseId": 1,        # no numeric → literal dot
    })
    _show("Nested filter", params)
    # numeric ID → each segment its own bracket
    assert params["filter[attributes][476][hasText]"] == "some text"
    # camelCase relation → dot kept literal in single bracket
    assert params["filter[commissionPhase.commissionPhaseId][eq]"] == "1"


def test_filter_or():
    params = build_params(
        filter_or=[
            {"name__contains": "STB"},
            {"status": "active"},
        ]
    )
    _show("filter_or", params)
    assert params["filterOr[0][name][contains]"] == "STB"
    assert params["filterOr[1][status][eq]"] == "active"


def test_filter_and():
    params = build_params(
        filter_and=[
            {"name__contains": "STB"},
            {"status": "active"},
        ]
    )
    _show("filter_and", params)
    assert params["filterAnd[0][name][contains]"] == "STB"
    assert params["filterAnd[1][status][eq]"] == "active"


def test_order():
    params = build_params(order={"name": "asc", "created_at": "desc"})
    _show("order", params)
    assert params["order[name]"] == "asc"
    assert params["order[created_at]"] == "desc"


def test_fields_and_extra_fields():
    params = build_params(fields=["id", "name", "email"], extra_fields=["address"])
    _show("fields + extra_fields", params)
    assert params["fields"] == "id,name,email"
    assert params["extra_fields"] == "address"


def test_pagination():
    params = build_params(limit=50, page=2, offset=100)
    _show("pagination", params)
    assert params["page[limit]"] == "50"
    assert params["page[number]"] == "2"
    assert params["page[offset]"] == "100"


def test_settings():
    params = build_params(with_relations=True, lang="pl", limit_to_my_settings=True)
    _show("settings", params)
    assert params["setting[with_relations]"] == "true"
    assert params["setting[lang]"] == "pl"
    assert params["setting[limit_to_my_settings]"] == "true"


def test_for_metadata():
    params = build_params(for_metadata={"id": 1, "type": "company"})
    _show("for_metadata", params)
    assert params["for[id]"] == "1"
    assert params["for[type]"] == "company"


def test_combined():
    params = build_params(
        filter={"name__contains": "STB", "attributes.476__hasText": "keyword"},
        filter_or=[
            {"name__contains": "STB"},
            {"status": "active"},
        ],
        order={"name": "asc"},
        fields=["id", "name"],
        limit=50,
        page=1,
        with_relations=True,
    )
    _show("combined", params)
    assert params["filter[name][contains]"] == "STB"
    assert params["filter[attributes][476][hasText]"] == "keyword"
    assert params["filterOr[0][name][contains]"] == "STB"
    assert params["filterOr[1][status][eq]"] == "active"
    assert params["order[name]"] == "asc"
    assert params["fields"] == "id,name"
    assert params["page[limit]"] == "50"
    assert params["page[number]"] == "1"
    assert params["setting[with_relations]"] == "true"


def test_import_guard():
    """Verify SWQueryBuilder is no longer importable from the package."""
    try:
        from swapi_client import SWQueryBuilder  # noqa: F401
        assert False, "SWQueryBuilder should not be importable"
    except ImportError:
        pass  # expected


if __name__ == "__main__":
    test_basic_filter()
    test_nested_filter()
    test_filter_or()
    test_filter_and()
    test_order()
    test_fields_and_extra_fields()
    test_pagination()
    test_settings()
    test_for_metadata()
    test_combined()
    test_import_guard()
    print("All tests passed!")
