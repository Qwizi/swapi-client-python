"""Product resources."""
from typing import TYPE_CHECKING

from ._base import SyncResource, AsyncResource

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


# ── Sync ──────────────────────────────────────────────────────────────────────

class SyncProductAttributesResource(SyncResource):
    _path = "/api/product_attributes"


class SyncProductCategoriesResource(SyncResource):
    _path = "/api/product_categories"


class SyncProductTemplatesResource(SyncResource):
    _path = "/api/product_templates"


class SyncProductsResource(SyncResource):
    _path = "/api/products"

    def __init__(self, client: "BaseSyncClient") -> None:
        super().__init__(client)
        self.attributes = SyncProductAttributesResource(client)
        self.categories = SyncProductCategoriesResource(client)
        self.templates = SyncProductTemplatesResource(client)

    def generate_pdf(self, product_id: int, template_id: int = 0) -> dict:
        return self._client.get(
            f"{self._path}/{product_id}/pdf",
            params={"template_id": template_id},
        )


# ── Async ─────────────────────────────────────────────────────────────────────

class AsyncProductAttributesResource(AsyncResource):
    _path = "/api/product_attributes"


class AsyncProductCategoriesResource(AsyncResource):
    _path = "/api/product_categories"


class AsyncProductTemplatesResource(AsyncResource):
    _path = "/api/product_templates"


class AsyncProductsResource(AsyncResource):
    _path = "/api/products"

    def __init__(self, client: "BaseAsyncClient") -> None:
        super().__init__(client)
        self.attributes = AsyncProductAttributesResource(client)
        self.categories = AsyncProductCategoriesResource(client)
        self.templates = AsyncProductTemplatesResource(client)

    async def generate_pdf(self, product_id: int, template_id: int = 0) -> dict:
        return await self._client.get(
            f"{self._path}/{product_id}/pdf",
            params={"template_id": template_id},
        )
