"""Place resources."""
from typing import TYPE_CHECKING

from ._base import SyncResource, AsyncResource

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


# ── Sync ──────────────────────────────────────────────────────────────────────

class SyncPlaceAttributesResource(SyncResource):
    _path = "/api/place_attributes"


class SyncPlacesResource(SyncResource):
    _path = "/api/places"

    def __init__(self, client: "BaseSyncClient") -> None:
        super().__init__(client)
        self.attributes = SyncPlaceAttributesResource(client)


# ── Async ─────────────────────────────────────────────────────────────────────

class AsyncPlaceAttributesResource(AsyncResource):
    _path = "/api/place_attributes"


class AsyncPlacesResource(AsyncResource):
    _path = "/api/places"

    def __init__(self, client: "BaseAsyncClient") -> None:
        super().__init__(client)
        self.attributes = AsyncPlaceAttributesResource(client)
