"""Kanban resources."""
from typing import TYPE_CHECKING

from ._base import SyncResource, AsyncResource

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


class SyncKanbansResource(SyncResource):
    _path = "/api/kanbans"


class AsyncKanbansResource(AsyncResource):
    _path = "/api/kanbans"
