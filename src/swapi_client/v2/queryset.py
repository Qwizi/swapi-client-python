"""
SWAPIQuerySet — wysokopoziomowa warstwa do filtrowania
i pobierania danych z SW API.

Obsługuje:
- Django-style filter(field__lookup=value)
- filter[...] (AND)
- fields / extra_fields
- setting[with_relations]
- setting[lang]
- order[field] = asc/desc
- page[limit], page[offset], page[number]
- for[field] = value
- values / values_list
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable, Type, TypeVar, Iterable

from swapi_client.v2.dynamic import DynamicObject
from .exceptions import SWAPIError, SWAPINotFoundError

M = TypeVar("M")


class SWAPIListResponse:
    """
    Reprezentuje odpowiedź typu LIST (`data: [...]`).
    Zapewnia:
    - items: lista modeli
    - meta: DynamicObject z metadanymi API (w tym meta.page.total_count)
    - errors/warnings/messages
    - iterowalność
    """
    def __init__(self, items, meta=None, errors=None, warnings=None, messages=None):
        self.items = items or []
        self.meta = DynamicObject(meta or {})
        self.errors = errors
        self.warnings = warnings
        self.messages = messages

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]
    
    def __repr__(self):
        return f"<SWAPIListResponse items={len(self.items)}>"


class SWAPIQuerySet(Iterable[M]):
    """
    ORM-like QuerySet for SWAPI.
    """

    LOOKUP_MAP = {
        "exact": "eq",
        "iexact": "ilike",
        "contains": "like",
        "icontains": "ilike",
        "startswith": "like",
        "istartswith": "ilike",
        "endswith": "like",
        "iendswith": "ilike",
        "gt": "gt",
        "gte": "gte",
        "lt": "lt",
        "lte": "lte",
        "in": "in",
        "isnull": "isNull",
    }
    VALID_LOOKUPS = set(LOOKUP_MAP.keys())

    def __init__(self, client, endpoint: str, model_cls: Type[M]):
        self.client = client
        self.endpoint = endpoint
        self.model_cls = model_cls

        # SWAPI settings
        self._with_relations: bool = False
        self._lang: str = "pl"
        self._limit_to_my_settings: bool = True
        self._with_editable_settings_for_action: Optional[str] = None

        # fields selection
        self._fields: Optional[List[str]] = None
        self._extra_fields: Optional[List[str]] = None

        # Django-style → SWAPI filters
        # przechowujemy już gotowe klucze typu:
        #   "filter[company.name][ilike]": "%stb%"
        self._filters: List[Dict[str, Any]] = []

        # Pagination / ordering (legacy: limit/offset/sort — jeśli potrzebujesz gdzie indziej)
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._order_by: Optional[str] = None

        # SWAPI pagination / order
        self._page_limit: Optional[int] = None
        self._page_offset: Optional[int] = None
        self._page_number: Optional[int] = None
        self._order: Dict[str, str] = {}  # order[field] = asc/desc

        # for[field] = value metadata
        self._for_fields: Optional[Dict[str, Any]] = None

        # values() / values_list()
        self._values_fields: Optional[List[str]] = None
        self._values_list_fields: Optional[List[str]] = None

        # Python-level post-filter support (na razie nieużywane – zostawiam hook)
        self._post_filters: List[Callable[[M], bool]] = []

    def __iter__(self):
        """
        SWAPIQuerySet is async-only. Use 'await queryset.all()' instead of iteration.
        """
        raise TypeError(
            "SWAPIQuerySet is async-only and cannot be iterated directly. "
            "Use 'await queryset.all()' to get results, then iterate over the returned object."
        )

    # ============================================================
    # SETTINGS
    # ============================================================
    def with_relations(self, value: bool = True) -> "SWAPIQuerySet":
        self._with_relations = value
        return self

    def lang(self, lang: str) -> "SWAPIQuerySet":
        self._lang = lang
        return self

    def limit_to_my_settings(self, value: bool = True) -> "SWAPIQuerySet":
        self._limit_to_my_settings = value
        return self

    def with_editable_settings_for_action(self, action: str) -> "SWAPIQuerySet":
        self._with_editable_settings_for_action = action
        return self

    # ============================================================
    # FIELD SELECTION
    # ============================================================
    def fields(self, *fields: str) -> "SWAPIQuerySet":
        self._fields = list(fields)
        return self

    def extra_fields(self, *fields: str) -> "SWAPIQuerySet":
        self._extra_fields = list(fields)
        return self

    # ============================================================
    # FILTERING — Django-style
    # ============================================================
    def filter(self, **kwargs) -> "SWAPIQuerySet":
        """
        Django-style filtracja:
            qs.filter(id=1)
            qs.filter(id__gte=10)
            qs.filter(commissionPhase__commissionPhaseId=95)
            qs.filter(company__name__icontains="stb")
        """
        for key, value in kwargs.items():
            parts = key.split("__")

            # Jeśli ostatni człon NIE jest lookupem — traktujemy całość jako pole, lookup=exact
            if parts[-1] not in self.VALID_LOOKUPS:
                field = ".".join(parts)  # np. commissionPhase.commissionPhaseId
                lookup = "exact"
            else:
                field = ".".join(parts[:-1])  # np. company.name
                lookup = parts[-1]

            swapi_op = self.LOOKUP_MAP[lookup]

            # isnull
            if lookup == "isnull":
                if value:
                    # isNull bez wartości
                    self._filters.append({f"filter[{field}][isNull]": ""})
                else:
                    self._filters.append({f"filter[{field}][isNotNull]": ""})
                continue

            # IN
            if lookup == "in":
                if not isinstance(value, (list, tuple)):
                    raise ValueError("Value for __in must be a list or tuple")
                value = ",".join(str(v) for v in value)

            # contains/startswith/endswith → modyfikacja value
            if lookup in ("contains", "icontains"):
                value = f"%{value}%"
            elif lookup in ("startswith", "istartswith"):
                value = f"{value}%"
            elif lookup in ("endswith", "iendswith"):
                value = f"%{value}"

            self._filters.append({f"filter[{field}][{swapi_op}]": value})

        return self

    def exclude(self, **kwargs) -> "SWAPIQuerySet":
        """
        Proste exclude w stylu:
            qs.exclude(id=1)
            qs.exclude(company__name__icontains="stb")

        Realizacja: zamiana eq → neq, ilike → notLike, isNull ↔ isNotNull itd.
        (na razie wersja prosta)
        """
        for key, value in kwargs.items():
            parts = key.split("__")

            if parts[-1] not in self.VALID_LOOKUPS:
                field = ".".join(parts)
                lookup = "exact"
            else:
                field = ".".join(parts[:-1])
                lookup = parts[-1]

            swapi_op = self.LOOKUP_MAP[lookup]

            # specjalna obsługa isnull
            if lookup == "isnull":
                if value:
                    # exclude(isnull=True) → isNotNull
                    self._filters.append({f"filter[{field}][isNotNull]": ""})
                else:
                    self._filters.append({f"filter[{field}][isNull]": ""})
                continue

            # prosta zamiana operatora na negatywny
            negate_map = {
                "eq": "neq",
                "ilike": "notLike",
                "like": "notLike",
                "gt": "lte",
                "gte": "lt",
                "lt": "gte",
                "lte": "gt",
                "in": "notIn",
            }
            neg_op = negate_map.get(swapi_op, "neq")

            if lookup == "in":
                if not isinstance(value, (list, tuple)):
                    raise ValueError("Value for __in must be a list or tuple")
                value = ",".join(str(v) for v in value)

            if lookup in ("contains", "icontains"):
                value = f"%{value}%"
            elif lookup in ("startswith", "istartswith"):
                value = f"{value}%"
            elif lookup in ("endswith", "iendswith"):
                value = f"%{value}"

            self._filters.append({f"filter[{field}][{neg_op}]": value})

        return self

    # ============================================================
    # PAGINATION — legacy + SWAPI
    # ============================================================
    def limit(self, n: int) -> "SWAPIQuerySet":
        self._limit = n
        return self

    def offset(self, n: int) -> "SWAPIQuerySet":
        self._offset = n
        return self

    def order_by(self, field: str) -> "SWAPIQuerySet":
        """
        Django-like: "-name" → desc, "name" → asc
        """
        direction = "asc"
        if field.startswith("-"):
            direction = "desc"
            field = field[1:]
        self._order[field] = direction
        self._order_by = None  # legacy pole niepotrzebne
        return self

    def page_limit(self, limit: int = 20) -> "SWAPIQuerySet":
        self._page_limit = limit
        return self

    def page_offset(self, offset: int) -> "SWAPIQuerySet":
        self._page_offset = offset
        return self

    def page_number(self, number: int = 1) -> "SWAPIQuerySet":
        self._page_number = number
        return self

    def order(self, field: str, direction: str = "asc") -> "SWAPIQuerySet":
        self._order[field] = direction
        return self

    # ============================================================
    # METADATA (for[field]=value)
    # ============================================================
    def for_(self, **fields: Any) -> "SWAPIQuerySet":
        if self._for_fields is None:
            self._for_fields = {}
        self._for_fields.update(fields)
        return self

    # ============================================================
    # VALUES / VALUES_LIST
    # ============================================================
    def values(self, *fields: str) -> "SWAPIQuerySet":
        self._values_fields = list(fields)
        self._values_list_fields = None
        return self

    def values_list(self, *fields: str) -> "SWAPIQuerySet":
        self._values_list_fields = list(fields)
        self._values_fields = None
        return self

    # ============================================================
    # BUILD PARAMS
    # ============================================================
    def _build_params(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}

        # settings
        params["setting[with_relations]"] = "true" if self._with_relations else "false"
        params["setting[lang]"] = self._lang
        # jeśli potrzebujesz kiedyś:
        # params["setting[limit_to_my_settings]"] = "true" if self._limit_to_my_settings else "false"
        # if self._with_editable_settings_for_action:
        #     params["setting[with_editable_settings_for_action]"] = self._with_editable_settings_for_action

        # fields / extra_fields
        if self._fields:
            params["fields"] = ",".join(self._fields)
        if self._extra_fields:
            params["extra_fields"] = ",".join(self._extra_fields)

        # FILTERS — już w formacie "filter[...][op]"
        for f in self._filters:
            params.update(f)

        # PAGINATION (legacy)
        if self._limit is not None:
            params["limit"] = self._limit
        if self._offset is not None:
            params["offset"] = self._offset
        if self._order_by:
            params["sort"] = self._order_by

        # SWAPI page[]
        if self._page_limit is not None:
            params["page[limit]"] = self._page_limit
        if self._page_offset is not None:
            params["page[offset]"] = self._page_offset
        if self._page_number is not None:
            params["page[number]"] = self._page_number

        # SWAPI order[field]
        for field, direction in self._order.items():
            params[f"order[{field}]"] = direction

        # for[field]
        if self._for_fields:
            for field, value in self._for_fields.items():
                params[f"for[{field}]"] = value

        return params

    # ============================================================
    # EXECUTION
    # ============================================================
    async def _fetch_raw(self, full_response: bool = False):
        """
        Pobiera dane z API.

        full_response = True → zwraca CAŁY response (data + meta + errors)
        full_response = False → zwraca TYLKO listę obiektów (data[])
        """
        params = self._build_params()
        resp = await self.client.get(self.endpoint, params=params)

        if full_response:
            return resp

        items = resp.get("data") or resp.get("items") or resp
        if isinstance(items, dict):
            return [items]
        return items

    async def all(self):
        """
        Pobiera listę obiektów:
        - zwraca SWAPIListResponse(items, meta, errors, warnings, messages)
        - obsługuje values() / values_list()
        - obsługuje ewentualne pythonowe _post_filters (hook)
        """
        resp = await self._fetch_raw(full_response=True)

        raw_items = resp.get("data") or []
        raw_meta = resp.get("meta") or {}
        errors = resp.get("errors")
        warnings = resp.get("warnings")
        messages = resp.get("messages")

        objs = [self.model_cls(item) for item in raw_items]

        # python-level post-filters (na razie nieużywane)
        for predicate in self._post_filters:
            objs = [o for o in objs if predicate(o)]

        # values()
        if self._values_fields is not None:
            return [
                {f: getattr(o, f, None) for f in self._values_fields}
                for o in objs
            ]

        # values_list()
        if self._values_list_fields is not None:
            return [
                tuple(getattr(o, f, None) for f in self._values_list_fields)
                for o in objs
            ]

        return SWAPIListResponse(
            items=objs,
            meta=raw_meta,
            errors=errors,
            warnings=warnings,
            messages=messages,
        )

    async def first(self) -> Optional[M]:
        qs = self.page_limit(1)
        result = await qs.all()
        return result[0] if len(result) > 0 else None

    async def get(self, id: Any) -> M:
        """
        get() — pobiera pojedynczy obiekt używając endpointu:
            GET /endpoint/{id}

        Używa TYLKO:
            - fields
            - extra_fields
            - setting[with_relations]
        """
        params: Dict[str, Any] = {}

        if self._fields:
            params["fields"] = ",".join(self._fields)
        if self._extra_fields:
            params["extra_fields"] = ",".join(self._extra_fields)
        if self._with_relations:
            params["setting[with_relations]"] = "true"

        try:
            data = await self.client.get(
                f"{self.endpoint}/{id}",
                params=params if params else None,
            )
        except SWAPIError as e:
            if "404" in str(e):
                raise SWAPINotFoundError(
                    f"{self.model_cls.__name__} id={id} not found"
                )
            raise

        obj_data = data.get("data") or data
        return self.model_cls(obj_data)

    async def exists(self) -> bool:
        return (await self.first()) is not None

    async def count(self) -> int:
        """
        Zwraca total_count z meta.page.total_count.
        Jeśli API nie zwróci total_count → fallback do liczenia elementów.
        """
        params = self._build_params()
        params["page[limit]"] = 1
        params["page[offset]"] = 0

        resp = await self.client.get(self.endpoint, params=params)

        meta = resp.get("meta") or {}
        page = meta.get("page") or {}

        total = page.get("total_count") or page.get("total")

        if total is not None:
            return int(total)

        raw_items = resp.get("data") or []
        return len(raw_items)

    async def get_raw(self, pk: int) -> Dict[str, Any]:
        url = f"{self.endpoint}/{pk}"
        return await self.client.get(url)

    async def create(self, **fields):
        """
        Tworzy nowy obiekt używając POST /endpoint.

        Przykład:
            comm = await Commission.objects().create(number="ZL-1")
        """
        if self.client is None:
            raise RuntimeError("QuerySet has no client assigned")

        payload = {"data": fields}
        resp = await self.client.post(self.endpoint, json=payload)
        data = resp.get("data") or resp

        return self.model_cls(data)

    async def meta(self):
        """
        Zwraca meta-dane endpointu:
            GET /endpoint/meta

        Zwracamy DynamicObject(resp["data"]), bo tam jest opis pól / modułu.
        """
        try:
            resp = await self.client.get(f"{self.endpoint}/meta")
        except SWAPIError as e:
            raise SWAPIError(f"Failed to fetch meta for {self.endpoint}: {e}")

        obj_data = resp.get("data") or resp
        return DynamicObject(obj_data)
