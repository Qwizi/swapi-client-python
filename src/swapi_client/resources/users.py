"""User resources."""
from typing import TYPE_CHECKING

from ._base import SyncResource, AsyncResource

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


# ── Sync ──────────────────────────────────────────────────────────────────────

class SyncUserAttributesResource(SyncResource):
    _path = "/api/user_attributes"


class SyncUserHistoriesResource(SyncResource):
    _path = "/api/user_users"

    def list(self, user_id: int, **kwargs) -> dict:
        return self._client.get(
            f"{self._path}/{user_id}/histories",
            params=self._params(**kwargs),
        )


class SyncUsersResource(SyncResource):
    _path = "/api/user_users"

    def __init__(self, client: "BaseSyncClient") -> None:
        super().__init__(client)
        self.attributes = SyncUserAttributesResource(client)
        self.histories = SyncUserHistoriesResource(client)


class SyncUserProfilesResource(SyncResource):
    _path = "/api/user_profiles"


# ── Async ─────────────────────────────────────────────────────────────────────

class AsyncUserAttributesResource(AsyncResource):
    _path = "/api/user_attributes"


class AsyncUserHistoriesResource(AsyncResource):
    _path = "/api/user_users"

    async def list(self, user_id: int, **kwargs) -> dict:
        return await self._client.get(
            f"{self._path}/{user_id}/histories",
            params=self._params(**kwargs),
        )


class AsyncUsersResource(AsyncResource):
    _path = "/api/user_users"

    def __init__(self, client: "BaseAsyncClient") -> None:
        super().__init__(client)
        self.attributes = AsyncUserAttributesResource(client)
        self.histories = AsyncUserHistoriesResource(client)


class AsyncUserProfilesResource(AsyncResource):
    _path = "/api/user_profiles"
