from typing import Any, Dict, Optional

from swapi_client.v2.dynamic import DynamicObject
from swapi_client.v2.exceptions import SWAPIError


class CoreQuerySet:
    """
    Minimalistyczny QuerySet dla endpointów typu /api/me,
    które nie mają filtrowania ani QuerySet DSL.

    Obsługuje:
    - get_me()
    - get_home()
    - get_settings()
    - get(path)
    - post(path, **payload)
    - patch(path, **payload)
    - delete(path)
    """

    def __init__(self, client, model_cls):
        self.client = client
        self.model_cls = model_cls

        self._fields = None
        self._extra_fields = None
        self._with_relations = False

    # ----------------------------
    #   Settings (opcjonalne)
    # ----------------------------
    def fields(self, *fields: str):
        self._fields = list(fields)
        return self

    def extra_fields(self, *fields: str):
        self._extra_fields = list(fields)
        return self

    def with_relations(self, value: bool = True):
        self._with_relations = value
        return self

    # ------------------------------------
    #   Helpers for building params
    # ------------------------------------
    def _build_params(self) -> Dict[str, Any]:
        params = {}

        # fields
        if self._fields:
            params["fields"] = ",".join(self._fields)

        # extra_fields
        if self._extra_fields:
            params["extra_fields"] = ",".join(self._extra_fields)

        # relations
        if self._with_relations:
            params["setting[with_relations]"] = "true"

        return params or None

    # ----------------------------
    #   GET predefined endpoints
    # ----------------------------
    async def get_me(self):
        return await self.get("api/me")

    async def get_home(self):
        return await self.get("api")

    async def get_settings(self):
        return await self.get("api/settings")

    # ----------------------------
    #   Generic GET
    # ----------------------------
    async def get(self, path: str):
        """
        Pobiera dane z dowolnego endpointu typu /api/xxx.
        Zwraca CoreModel z dynamicznymi polami.
        """

        if not path.startswith("/"):
            path = "/" + path

        params = self._build_params()

        try:
            resp = await self.client.get(path, params=params)
        except SWAPIError as e:
            raise type(e)(f"GET {path} failed: {e}") from e

        data = resp.get("data") or resp
        return self.model_cls(data)

    # ----------------------------
    #   Generic POST
    # ----------------------------
    async def post(self, path: str, **fields):
        if not path.startswith("/"):
            path = "/" + path

        payload = {"data": fields}

        try:
            resp = await self.client.post(path, json=payload)
        except SWAPIError as e:
            raise type(e)(f"POST {path} failed: {e}") from e

        data = resp.get("data") or resp
        return self.model_cls(data)

    # ----------------------------
    #   Generic PATCH
    # ----------------------------
    async def patch(self, path: str, **fields):
        if not path.startswith("/"):
            path = "/" + path

        payload = {"data": fields}

        try:
            resp = await self.client.patch(path, json=payload)
        except SWAPIError as e:
            raise type(e)(f"PATCH {path} failed: {e}") from e

        data = resp.get("data") or resp
        return self.model_cls(data)

    # ----------------------------
    #   Generic DELETE
    # ----------------------------
    async def delete(self, path: str):
        if not path.startswith("/"):
            path = "/" + path

        try:
            resp = await self.client.delete(path)
        except SWAPIError as e:
            raise type(e)(f"DELETE {path} failed: {e}") from e

        return resp