"""
Q objects for building complex SWAPI filters (Django-style).

Przykład:

    from swapi_sdk.q import Q

    q = (Q(status__eq="open") | Q(status__eq="pending")) & Q(priority__eq="high")

    qs = Commission.objects().filter(q)
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


class Q:
    """
    Prosty odpowiednik Django Q:

        Q(field__op=value) & Q(...)
        Q(...) | Q(...)
        ~Q(...)

    Obsługiwane operatory (po stronie SWAPI w query params):
        eq, neq, lt, lte, gt, gte,
        in, notIn,
        like, ilike, notLike, hasText,
        isNull, isNotNull
    """

    AND = "AND"
    OR = "OR"

    def __init__(self, **filters: Any):
        # Leaf filters, np. {"status__eq": "open", "priority__eq": "high"}
        self.filters: Dict[str, Any] = filters

        # Zagnieżdżone Q (children)
        self.children: List["Q"] = []

        # Łącznik między childami: AND / OR
        self.connector: str = Q.AND

        # Czy Q jest zanegowane (~Q)
        self.negated: bool = False

    # ----------------------------------
    #  Operatory logiczne
    # ----------------------------------
    def __and__(self, other: "Q") -> "Q":
        """
        Łączy dwa Q logicznym AND:
            q1 & q2
        """
        q = Q()
        q.children = [self, other]
        q.connector = Q.AND
        return q

    def __or__(self, other: "Q") -> "Q":
        """
        Łączy dwa Q logicznym OR:
            q1 | q2
        """
        q = Q()
        q.children = [self, other]
        q.connector = Q.OR
        return q

    def __invert__(self) -> "Q":
        """
        Negacja Q:
            ~Q(...)
        """
        q = Q()
        q.children = [self]
        q.negated = True
        return q

    # ----------------------------------
    #  Helpers
    # ----------------------------------
    def is_leaf(self) -> bool:
        """
        Leaf = ma filters, nie ma children.
        """
        return bool(self.filters) and not self.children

    def __repr__(self) -> str:
        if self.is_leaf():
            base = f"Q({self.filters})"
        else:
            base = f"Q({self.connector}, children={self.children})"
        if self.negated:
            return f"~{base}"
        return base


# Mapowanie operatorów na ich negacje —
# używane przy budowaniu filter[...] lub do post-filteringu po stronie Pythona.
NEGATE_OP: Dict[str, str] = {
    "eq": "neq",
    "neq": "eq",
    "lt": "gte",
    "lte": "gt",
    "gt": "lte",
    "gte": "lt",
    "like": "notLike",
    "notLike": "like",
    "ilike": "notLike",
    "hasText": "notLike",  # brak idealnego odpowiednika, ale działa jako negacja tekstowa
    "in": "notIn",
    "notIn": "in",
    "isNull": "isNotNull",
    "isNotNull": "isNull",
}
