"""Base resource classes providing standard CRUD operations."""
from typing import Any, Optional, TYPE_CHECKING

from .._params import build_params

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


class SyncResource:
    """Base class for synchronous API resources.

    Subclasses must define ``_path`` (e.g. ``"/api/products"``).
    """

    _path: str = ""

    def __init__(self, client: "BaseSyncClient") -> None:
        self._client = client

    # ── helpers ───────────────────────────────────────────────────────────────

    def _params(self, **kwargs) -> dict[str, str]:
        return build_params(**kwargs)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def list(self, **kwargs) -> dict:
        return self._client.get(self._path, params=self._params(**kwargs))

    def retrieve(self, id: Any, **kwargs) -> dict:
        return self._client.get(f"{self._path}/{id}", params=self._params(**kwargs))

    def create(self, data: dict, **kwargs) -> dict:
        return self._client.post(self._path, json=data, params=self._params(**kwargs))

    def update(self, id: Any, data: dict, **kwargs) -> dict:
        return self._client.put(f"{self._path}/{id}", json=data, params=self._params(**kwargs))

    def partial_update(self, id: Any, data: dict, **kwargs) -> dict:
        return self._client.patch(f"{self._path}/{id}", json=data, params=self._params(**kwargs))

    def delete(self, id: Any, **kwargs) -> dict:
        return self._client.delete(f"{self._path}/{id}", params=self._params(**kwargs))

    def bulk_update(self, data: dict, **kwargs) -> dict:
        return self._client.put(self._path, json=data, params=self._params(**kwargs))

    def bulk_delete(self, **kwargs) -> dict:
        return self._client.delete(self._path, params=self._params(**kwargs))

    def meta(self, **kwargs) -> dict:
        return self._client.get(f"{self._path}/meta", params=self._params(**kwargs))

    def autoselect(self, **kwargs) -> dict:
        return self._client.get(f"{self._path}/autoselect", params=self._params(**kwargs))

    def all(self, **kwargs) -> list:
        """Fetch all pages and return a flat list of items."""
        items: list = []
        page = 1
        limit = kwargs.pop("limit", 100)
        while True:
            response = self.list(page=page, limit=limit, **kwargs)
            data = response.get("data", [])
            items.extend(data)
            meta = response.get("meta", {})
            total = meta.get("total", 0)
            if not data or len(items) >= total:
                break
            page += 1
        return items


class AsyncResource:
    """Base class for asynchronous API resources.

    Subclasses must define ``_path`` (e.g. ``"/api/products"``).
    """

    _path: str = ""

    def __init__(self, client: "BaseAsyncClient") -> None:
        self._client = client

    # ── helpers ───────────────────────────────────────────────────────────────

    def _params(self, **kwargs) -> dict[str, str]:
        return build_params(**kwargs)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def list(self, **kwargs) -> dict:
        return await self._client.get(self._path, params=self._params(**kwargs))

    async def retrieve(self, id: Any, **kwargs) -> dict:
        return await self._client.get(f"{self._path}/{id}", params=self._params(**kwargs))

    async def create(self, data: dict, **kwargs) -> dict:
        return await self._client.post(self._path, json=data, params=self._params(**kwargs))

    async def update(self, id: Any, data: dict, **kwargs) -> dict:
        return await self._client.put(f"{self._path}/{id}", json=data, params=self._params(**kwargs))

    async def partial_update(self, id: Any, data: dict, **kwargs) -> dict:
        return await self._client.patch(f"{self._path}/{id}", json=data, params=self._params(**kwargs))

    async def delete(self, id: Any, **kwargs) -> dict:
        return await self._client.delete(f"{self._path}/{id}", params=self._params(**kwargs))

    async def bulk_update(self, data: dict, **kwargs) -> dict:
        return await self._client.put(self._path, json=data, params=self._params(**kwargs))

    async def bulk_delete(self, **kwargs) -> dict:
        return await self._client.delete(self._path, params=self._params(**kwargs))

    async def meta(self, **kwargs) -> dict:
        return await self._client.get(f"{self._path}/meta", params=self._params(**kwargs))

    async def autoselect(self, **kwargs) -> dict:
        return await self._client.get(f"{self._path}/autoselect", params=self._params(**kwargs))

    async def all(self, **kwargs) -> list:
        """Fetch all pages and return a flat list of items."""
        items: list = []
        page = 1
        limit = kwargs.pop("limit", 100)
        while True:
            response = await self.list(page=page, limit=limit, **kwargs)
            data = response.get("data", [])
            items.extend(data)
            meta = response.get("meta", {})
            total = meta.get("total", 0)
            if not data or len(items) >= total:
                break
            page += 1
        return items
