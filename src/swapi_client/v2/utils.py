"""
Utility functions used across SWAPI SDK.
"""

from typing import Tuple


def parse_filter_key(key: str) -> Tuple[str, str]:
    """
    Parse Django-style filter key into (field, operator).

    Przykłady:
        "status__eq"   -> ("status", "eq")
        "name__like"   -> ("name", "like")
        "id"           -> ("id", "eq")
        "company.name__ilike" -> ("company.name", "ilike")

    Jeżeli użytkownik nie poda operatora, używamy "eq".
    """
    parts = key.split("__", 1)
    if len(parts) == 1:
        return parts[0], "eq"
    return parts[0], parts[1]


def is_iterable_but_not_string(value) -> bool:
    """
    True gdy wartość jest listą/krotką/setem, ale nie stringiem.
    Używane do obsługi operatorów typu 'in' / 'notIn'.
    """
    if isinstance(value, str):
        return False
    return isinstance(value, (list, tuple, set))


def list_to_csv(values) -> str:
    """
    Konwertuje listę/krotkę/set na CSV, np.:
        [1, 2, 3] -> "1,2,3"
    """
    return ",".join(str(v) for v in values)