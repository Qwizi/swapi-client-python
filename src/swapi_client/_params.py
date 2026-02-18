"""Query parameter builder for SW API requests.

Converts kwargs into a flat dict of URL query parameters.
"""
from typing import Any


def _parse_filter_key(key: str) -> tuple[list[str] | str, str]:
    """Parse a filter key into field (str or list) and operator.

    If any dot-separated segment is purely numeric, the field is split into a
    list — each segment becomes its own bracket pair.
    Otherwise the dot is treated as literal and the whole field stays in one bracket.

    Examples:
        "name__contains"                    -> ("name", "contains")
        "status"                            -> ("status", "eq")
        "attributes.476__hasText"           -> (["attributes", "476"], "hasText")
        "commissionPhase.commissionPhaseId" -> ("commissionPhase.commissionPhaseId", "eq")
    """
    if "__" in key:
        field, op = key.rsplit("__", 1)
    else:
        field, op = key, "eq"

    parts = field.split(".")
    if len(parts) > 1 and any(p.isdigit() for p in parts):
        return parts, op  # numeric segment → multiple brackets
    return field, op     # all non-numeric → literal dot in single bracket


def _filter_key(prefix: str, field: list[str] | str, op: str) -> str:
    """Build the bracket-notation filter key string."""
    if isinstance(field, list):
        brackets = "".join(f"[{p}]" for p in field)
    else:
        brackets = f"[{field}]"
    return f"{prefix}{brackets}[{op}]"


def _filter_value(value: Any, op: str) -> str:
    if op in ("isNull", "isNotNull"):
        return ""
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return str(value)


def build_params(**kwargs) -> dict[str, str]:
    """Convert keyword arguments to URL query parameters dict.

    Supported kwargs:
        filter          dict    {"name__contains": "STB", "id__gt": 10}
        filter_or       list    [{"name__contains": "STB"}, {"status": "active"}]
        filter_and      list    [{"name__contains": "STB"}, {"status": "active"}]
        order           dict    {"name": "asc"}
        fields          list    ["id", "name"]
        extra_fields    list    ["address"]
        limit           int     50   -> page[limit]=50
        page            int     1    -> page[number]=1
        offset          int     0    -> page[offset]=0
        with_relations  bool    True -> setting[with_relations]=true
        with_cache      bool    False-> setting[with_cache]=false
        limit_to_my_settings bool -> setting[limit_to_my_settings]=true
        lang            str     "pl" -> setting[lang]=pl
        for_metadata    dict    {"id": 1} -> for[id]=1
    """
    params: dict[str, str] = {}

    # filter
    if "filter" in kwargs:
        for key, value in kwargs["filter"].items():
            field, op = _parse_filter_key(key)
            params[_filter_key("filter", field, op)] = _filter_value(value, op)

    # filter_or
    if "filter_or" in kwargs:
        for idx, group in enumerate(kwargs["filter_or"]):
            for key, value in group.items():
                field, op = _parse_filter_key(key)
                params[_filter_key(f"filterOr[{idx}]", field, op)] = _filter_value(value, op)

    # filter_and
    if "filter_and" in kwargs:
        for idx, group in enumerate(kwargs["filter_and"]):
            for key, value in group.items():
                field, op = _parse_filter_key(key)
                params[_filter_key(f"filterAnd[{idx}]", field, op)] = _filter_value(value, op)

    # order
    if "order" in kwargs:
        for field, direction in kwargs["order"].items():
            params[f"order[{field}]"] = direction

    # fields
    if "fields" in kwargs:
        params["fields"] = ",".join(kwargs["fields"])

    # extra_fields
    if "extra_fields" in kwargs:
        params["extra_fields"] = ",".join(kwargs["extra_fields"])

    # pagination
    if "limit" in kwargs:
        params["page[limit]"] = str(kwargs["limit"])
    if "page" in kwargs:
        params["page[number]"] = str(kwargs["page"])
    if "offset" in kwargs:
        params["page[offset]"] = str(kwargs["offset"])

    # settings
    if "with_relations" in kwargs:
        params["setting[with_relations]"] = str(kwargs["with_relations"]).lower()
    if "with_cache" in kwargs:
        params["setting[with_cache]"] = str(kwargs["with_cache"]).lower()
    if "limit_to_my_settings" in kwargs:
        params["setting[limit_to_my_settings]"] = str(kwargs["limit_to_my_settings"]).lower()
    if "lang" in kwargs:
        params["setting[lang]"] = kwargs["lang"]

    # for_metadata
    if "for_metadata" in kwargs:
        for field, value in kwargs["for_metadata"].items():
            params[f"for[{field}]"] = str(value)

    return params
