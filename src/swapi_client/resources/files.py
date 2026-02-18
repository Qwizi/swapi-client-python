"""File resources."""
from typing import TYPE_CHECKING

from ._base import SyncResource, AsyncResource

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


# ── Sync ──────────────────────────────────────────────────────────────────────

class SyncFileDirectoriesResource(SyncResource):
    _path = "/api/file_directories"


class SyncFilesResource(SyncResource):
    _path = "/api/files"

    def __init__(self, client: "BaseSyncClient") -> None:
        super().__init__(client)
        self.directories = SyncFileDirectoriesResource(client)

    def upload(self, files: dict, mode: int = 0) -> dict:
        return self._client.post(
            f"{self._path}/upload",
            files=files,
            params={"mode": mode},
        )

    def upload_from_urls(self, urls: list[str]) -> dict:
        return self._client.post(
            f"{self._path}/upload_from_urls",
            json={"urls": urls},
        )


# ── Async ─────────────────────────────────────────────────────────────────────

class AsyncFileDirectoriesResource(AsyncResource):
    _path = "/api/file_directories"


class AsyncFilesResource(AsyncResource):
    _path = "/api/files"

    def __init__(self, client: "BaseAsyncClient") -> None:
        super().__init__(client)
        self.directories = AsyncFileDirectoriesResource(client)

    async def upload(self, files: dict, mode: int = 0) -> dict:
        return await self._client.post(
            f"{self._path}/upload",
            files=files,
            params={"mode": mode},
        )

    async def upload_from_urls(self, urls: list[str]) -> dict:
        return await self._client.post(
            f"{self._path}/upload_from_urls",
            json={"urls": urls},
        )
