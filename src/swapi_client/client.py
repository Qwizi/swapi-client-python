"""SW API client — public entry points.

Usage (sync):
    with SWApiClient("https://api.url") as client:
        client.auth.login(client_id="...", auth_token="...", login="...", password="...")
        result = client.account.companies.list(filter={"name__contains": "test"}, limit=10)

Usage (async):
    async with AsyncSWApiClient("https://api.url") as client:
        await client.auth.login(client_id="...", auth_token="...", login="...", password="...")
        result = await client.account.companies.list(filter={"name__contains": "test"}, limit=10)
"""
from typing import Optional

from ._http import BaseSyncClient, BaseAsyncClient
from .resources import (
    SyncAuthResource,
    AsyncAuthResource,
    SyncAccountResource,
    AsyncAccountResource,
    SyncCommissionsResource,
    AsyncCommissionsResource,
    SyncFilesResource,
    AsyncFilesResource,
    SyncKanbansResource,
    AsyncKanbansResource,
    SyncPlacesResource,
    AsyncPlacesResource,
    SyncProductsResource,
    AsyncProductsResource,
    SyncServicedProductsResource,
    AsyncServicedProductsResource,
    SyncUsersResource,
    AsyncUsersResource,
    SyncUserProfilesResource,
    AsyncUserProfilesResource,
)


class SWApiClient(BaseSyncClient):
    """Synchronous SW API client.

    Use as a context manager::

        with SWApiClient("https://api.url") as client:
            client.auth.login(...)
    """

    def __init__(
        self,
        api_url: str,
        token: Optional[str] = None,
        timeout: int = 30,
        user_agent: str = "SWApiClient/3.0 (Python)",
    ):
        super().__init__(api_url, token=token, timeout=timeout, user_agent=user_agent)
        self.auth = SyncAuthResource(self)
        self.account = SyncAccountResource(self)
        self.commissions = SyncCommissionsResource(self)
        self.files = SyncFilesResource(self)
        self.kanbans = SyncKanbansResource(self)
        self.places = SyncPlacesResource(self)
        self.products = SyncProductsResource(self)
        self.serviced_products = SyncServicedProductsResource(self)
        self.users = SyncUsersResource(self)
        self.user_profiles = SyncUserProfilesResource(self)

    def me(self) -> dict:
        """Return data of the currently authenticated user."""
        return self.get("/api/me")


class AsyncSWApiClient(BaseAsyncClient):
    """Asynchronous SW API client.

    Use as an async context manager::

        async with AsyncSWApiClient("https://api.url") as client:
            await client.auth.login(...)
    """

    def __init__(
        self,
        api_url: str,
        token: Optional[str] = None,
        timeout: int = 30,
        user_agent: str = "SWApiClient/3.0 (Python)",
    ):
        super().__init__(api_url, token=token, timeout=timeout, user_agent=user_agent)
        self.auth = AsyncAuthResource(self)
        self.account = AsyncAccountResource(self)
        self.commissions = AsyncCommissionsResource(self)
        self.files = AsyncFilesResource(self)
        self.kanbans = AsyncKanbansResource(self)
        self.places = AsyncPlacesResource(self)
        self.products = AsyncProductsResource(self)
        self.serviced_products = AsyncServicedProductsResource(self)
        self.users = AsyncUsersResource(self)
        self.user_profiles = AsyncUserProfilesResource(self)

    async def me(self) -> dict:
        """Return data of the currently authenticated user."""
        return await self.get("/api/me")
