"""Authentication resources."""
from typing import TYPE_CHECKING

from ..exceptions import SWException

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


class SyncAuthResource:
    def __init__(self, client: "BaseSyncClient") -> None:
        self._client = client

    def login(self, client_id: str, auth_token: str, login: str, password: str) -> str:
        data = {
            "clientId": client_id,
            "authToken": auth_token,
            "login": login,
            "password": password,
        }
        response = self._client.post("/_/security/login", json=data)
        token = response.get("token")
        if not token:
            raise SWException("Login failed: token not found in response.")
        self._client.set_token(token)
        return token

class AsyncAuthResource:
    def __init__(self, client: "BaseAsyncClient") -> None:
        self._client = client

    async def login(self, client_id: str, auth_token: str, login: str, password: str) -> str:
        data = {
            "clientId": client_id,
            "authToken": auth_token,
            "login": login,
            "password": password,
        }
        response = await self._client.post("/_/security/login", json=data)
        token = response.get("token")
        if not token:
            raise SWException("Login failed: token not found in response.")
        self._client.set_token(token)
        return token

