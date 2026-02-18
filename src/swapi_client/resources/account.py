"""Account resources: companies and users."""
from typing import TYPE_CHECKING

from ._base import SyncResource, AsyncResource

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


# ── Account Companies ─────────────────────────────────────────────────────────

class SyncAccountCompaniesAttributesResource(SyncResource):
    _path = "/api/account_company_attributes"


class SyncAccountCompaniesHistoriesResource(SyncResource):
    _path = "/api/account_companies"

    def list(self, company_id: int, **kwargs) -> dict:
        return self._client.get(
            f"{self._path}/{company_id}/histories",
            params=self._params(**kwargs),
        )


class SyncAccountCompaniesResource(SyncResource):
    _path = "/api/account_companies"

    def __init__(self, client: "BaseSyncClient") -> None:
        super().__init__(client)
        self.attributes = SyncAccountCompaniesAttributesResource(client)
        self.histories = SyncAccountCompaniesHistoriesResource(client)

    def gus_update(self, company_id: int, data: dict) -> dict:
        return self._client.put(f"{self._path}/{company_id}/gus", json=data)

    def odbc_reports(self, company_id: int, **kwargs) -> dict:
        return self._client.get(
            f"{self._path}/{company_id}/odbc_reports",
            params=self._params(**kwargs),
        )

    def email_messages(self, company_id: int, **kwargs) -> dict:
        return self._client.get(
            f"{self._path}/{company_id}/email_messages",
            params=self._params(**kwargs),
        )


# ── Account Users ─────────────────────────────────────────────────────────────

class SyncAccountUsersAttributesResource(SyncResource):
    _path = "/api/account_user_attributes"


class SyncAccountUsersHistoriesResource(SyncResource):
    _path = "/api/account_users"

    def list(self, user_id: int, **kwargs) -> dict:
        return self._client.get(
            f"{self._path}/{user_id}/histories",
            params=self._params(**kwargs),
        )


class SyncAccountUsersResource(SyncResource):
    _path = "/api/account_users"

    def __init__(self, client: "BaseSyncClient") -> None:
        super().__init__(client)
        self.attributes = SyncAccountUsersAttributesResource(client)
        self.histories = SyncAccountUsersHistoriesResource(client)


# ── Account (container) ───────────────────────────────────────────────────────

class SyncAccountResource:
    def __init__(self, client: "BaseSyncClient") -> None:
        self.companies = SyncAccountCompaniesResource(client)
        self.users = SyncAccountUsersResource(client)


# ═════════════════════════════════════════════════════════════════════════════
# ASYNC
# ═════════════════════════════════════════════════════════════════════════════

class AsyncAccountCompaniesAttributesResource(AsyncResource):
    _path = "/api/account_company_attributes"


class AsyncAccountCompaniesHistoriesResource(AsyncResource):
    _path = "/api/account_companies"

    async def list(self, company_id: int, **kwargs) -> dict:
        return await self._client.get(
            f"{self._path}/{company_id}/histories",
            params=self._params(**kwargs),
        )


class AsyncAccountCompaniesResource(AsyncResource):
    _path = "/api/account_companies"

    def __init__(self, client: "BaseAsyncClient") -> None:
        super().__init__(client)
        self.attributes = AsyncAccountCompaniesAttributesResource(client)
        self.histories = AsyncAccountCompaniesHistoriesResource(client)

    async def gus_update(self, company_id: int, data: dict) -> dict:
        return await self._client.put(f"{self._path}/{company_id}/gus", json=data)

    async def odbc_reports(self, company_id: int, **kwargs) -> dict:
        return await self._client.get(
            f"{self._path}/{company_id}/odbc_reports",
            params=self._params(**kwargs),
        )

    async def email_messages(self, company_id: int, **kwargs) -> dict:
        return await self._client.get(
            f"{self._path}/{company_id}/email_messages",
            params=self._params(**kwargs),
        )


class AsyncAccountUsersAttributesResource(AsyncResource):
    _path = "/api/account_user_attributes"


class AsyncAccountUsersHistoriesResource(AsyncResource):
    _path = "/api/account_users"

    async def list(self, user_id: int, **kwargs) -> dict:
        return await self._client.get(
            f"{self._path}/{user_id}/histories",
            params=self._params(**kwargs),
        )


class AsyncAccountUsersResource(AsyncResource):
    _path = "/api/account_users"

    def __init__(self, client: "BaseAsyncClient") -> None:
        super().__init__(client)
        self.attributes = AsyncAccountUsersAttributesResource(client)
        self.histories = AsyncAccountUsersHistoriesResource(client)


class AsyncAccountResource:
    def __init__(self, client: "BaseAsyncClient") -> None:
        self.companies = AsyncAccountCompaniesResource(client)
        self.users = AsyncAccountUsersResource(client)
