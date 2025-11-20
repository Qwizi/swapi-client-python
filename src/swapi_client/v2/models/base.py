"""
Base APIModel for SWAPI SDK.

Zapewnia:
- dynamiczne atrybuty z JSON
- dirty-tracking (zmienione pola)
- create(), save(), delete()
- objects() → SWAPIQuerySet
"""

from __future__ import annotations

from typing import Any, Dict, Type, TypeVar, Optional

from ..queryset import SWAPIQuerySet
from ..exceptions import SWAPIError
from ..dynamic import DynamicObject, DynamicList

M = TypeVar("M", bound="APIModel")




class APIModel:
    """
    Bazowy model SWAPI — odpowiednik Django Model, ale działający po REST.

    - dynamiczne pola (wszystko z JSON trafia do __dict__)
    - dirty tracking
    - save() → PATCH / endpoint/{id}
    - create() → POST / endpoint
    - delete() → DELETE / endpoint/{id}
    """

    endpoint: str = ""         # przykład: "/commissions"
    client = None              # SWAPIClient
    pk_field: str = "id"       # standardowo "id", ale można zmienić

    def __init__(self, data: Dict[str, Any]):
        # surowy JSON ze SWAPI
        self._raw: Dict[str, Any] = data

       # dynamiczne pola + wrap
        for key, value in data.items():
            super().__setattr__(key, self._wrap_dynamic(value))

        # dirty tracking
        self._original: Dict[str, Any] = dict(data)
        self._dirty: Dict[str, Any] = {}


    def _wrap_dynamic(self, value):
        if isinstance(value, dict):
            return DynamicObject(value)
        if isinstance(value, list):
            return DynamicList(value)
        return value

    # ---------------------------------------------------------
    # DYNAMICZNE ATRYBUTY I DIRTY TRACKING
    # ---------------------------------------------------------
    def __setattr__(self, key: str, value: Any):
        """
        Każde ustawienie pola zapisujemy jako dirty,
        o ile obiekt jest już zainicjalizowany.
        """
        # W czasie inicjalizacji "__dict__" jeszcze nie istnieje
        in_init = not hasattr(self, "_original")

        super().__setattr__(key, value)

        if not in_init:
            # tylko jeśli zmieniamy pole z JSON
            if key in self._original and self._original[key] != value:
                self._dirty[key] = value

    def __getattr__(self, item: str) -> Any:
        """
        Pozwala pobierać dowolne dynamiczne pole.
        """
        try:
            return self.__dict__[item]
        except KeyError:
            raise AttributeError(f"{self.__class__.__name__} has no attribute '{item}'")

    # ---------------------------------------------------------
    # PROPERTIES
    # ---------------------------------------------------------
    @property
    def pk(self) -> Optional[Any]:
        return getattr(self, self.pk_field, None)

    # ---------------------------------------------------------
    # QUERYSET
    # ---------------------------------------------------------
    @classmethod
    def objects(cls) -> SWAPIQuerySet:
        if cls.client is None:
            raise RuntimeError(f"{cls.__name__}.client is not set")
        return SWAPIQuerySet(
            client=cls.client,
            endpoint=cls.endpoint,
            model_cls=cls,
        )

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------
    async def save(self) -> M:
        """
        Save model to SWAPI.

        POST → gdy obiekt nie ma ID  
        PATCH → gdy istnieje i są dirty fields
        """
        if self.client is None:
            raise RuntimeError("Model has no API client assigned")

        # CREATE (POST)
        if self.pk is None:
            payload = {"data": self._as_payload(full=True)}
            resp = await self.client.post(self.endpoint, json=payload)

            data = resp.get("data") or resp
            return self._reload_from_data(data)

        # UPDATE (PATCH)
        if not self._dirty:
            return self  # nic nie zmieniono

        payload = {"data": self._dirty}
        resp = await self.client.patch(f"{self.endpoint}/{self.pk}", json=payload)

        data = resp.get("data") or resp
        return self._reload_from_data(data)

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------
    async def delete(self) -> None:
        if self.pk is None:
            raise SWAPIError("Cannot delete object without primary key")

        await self.client.delete(f"{self.endpoint}/{self.pk}")

    # ---------------------------------------------------------
    # SERIALIZATION
    # ---------------------------------------------------------
    def _as_payload(self, full: bool = False) -> Dict[str, Any]:
        """
        Zwraca dane do POST/PATCH.
        """
        def _serialize(value: Any) -> Any:
            if isinstance(value, DynamicObject):
                return value.to_dict()
            if isinstance(value, DynamicList):
                return value.to_list()
            return value

        if full:
            # POST
            return {
                k: _serialize(v)
                for k, v in self.__dict__.items()
                if not k.startswith("_")
            }

        # PATCH (dirty only)
        return {k: _serialize(v) for k, v in self._dirty.items()}

    def _reload_from_data(self, data: Dict[str, Any]):
        self._raw = data
        self._original = {}
        self._dirty = {}

        for key, value in data.items():
            wrapped = self._wrap_dynamic(value)
            super().__setattr__(key, wrapped)
            self._original[key] = wrapped

        return self

    # ---------------------------------------------------------
    # REPRESENTATION
    # ---------------------------------------------------------
    def __repr__(self):
        # Jeśli obiekt nie ma _data (np. SWAPIListResponse.items jest listą),
        # to zwracamy prosty repr aby uniknąć błędów.
        if not hasattr(self, "_data") or not isinstance(self._data, dict):
            return f"<{self.__class__.__name__}>"

        cls = self.__class__.__name__
        pk = self._data.get("id") or self._data.get("pk")

        field_names = ", ".join(self._data.keys())
        if len(field_names) > 120:
            field_names = field_names[:117] + "..."

        return f"<{cls} pk={pk} fields={field_names}>"
