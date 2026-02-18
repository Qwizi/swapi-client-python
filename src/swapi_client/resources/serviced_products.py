"""Serviced product resources."""
from typing import TYPE_CHECKING

from ._base import SyncResource, AsyncResource

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


# ── Sync ──────────────────────────────────────────────────────────────────────

class SyncServicedProductAttributesResource(SyncResource):
    _path = "/api/serviced_product_attributes"


class SyncServicedProductsResource(SyncResource):
    _path = "/api/serviced_products"

    def __init__(self, client: "BaseSyncClient") -> None:
        super().__init__(client)
        self.attributes = SyncServicedProductAttributesResource(client)

    def generate_pdf(self, product_id: int, template_id: int = 0) -> dict:
        return self._client.get(
            f"{self._path}/{product_id}/pdf",
            params={"template_id": template_id},
        )


# ── Async ─────────────────────────────────────────────────────────────────────

class AsyncServicedProductAttributesResource(AsyncResource):
    _path = "/api/serviced_product_attributes"


class AsyncServicedProductsResource(AsyncResource):
    _path = "/api/serviced_products"

    def __init__(self, client: "BaseAsyncClient") -> None:
        super().__init__(client)
        self.attributes = AsyncServicedProductAttributesResource(client)

    async def generate_pdf(self, product_id: int, template_id: int = 0) -> dict:
        return await self._client.get(
            f"{self._path}/{product_id}/pdf",
            params={"template_id": template_id},
        )
