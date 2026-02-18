"""Low-level HTTP clients for SW API.

BaseSyncClient  – wraps httpx.Client (synchronous)
BaseAsyncClient – wraps httpx.AsyncClient (asynchronous)
"""
from typing import Any, Optional

import httpx

from .exceptions import SWException, SWConnectionError, _http_error_for_status

_DEFAULT_USER_AGENT = "SWApiClient/3.0 (Python)"


def _parse_response_data(response: httpx.Response) -> Any:
    """Try to parse response body as JSON, fall back to text."""
    try:
        return response.json()
    except Exception:
        return response.text


def _raise_for_status(response: httpx.Response) -> None:
    """Raise the most specific SWHTTPError subclass for non-2xx responses."""
    if response.is_success:
        return
    response_data = _parse_response_data(response)
    if isinstance(response_data, dict):
        message = response_data.get("message") or response_data.get("error") or response.text
    else:
        message = response.text
    raise _http_error_for_status(response.status_code, message, response_data)


class BaseSyncClient:
    """Synchronous HTTP client using httpx.Client.

    Use as a context manager:
        with BaseSyncClient(api_url) as client:
            data = client.get("/api/resource")
    """

    def __init__(
        self,
        api_url: str,
        token: Optional[str] = None,
        timeout: int = 30,
        user_agent: str = _DEFAULT_USER_AGENT,
    ):
        self.api_url = api_url.rstrip("/")
        self._token = token
        self.timeout = timeout
        self.user_agent = user_agent
        self._client: Optional[httpx.Client] = None

    # ── context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "BaseSyncClient":
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.Client(
            base_url=self.api_url,
            headers=headers,
            timeout=self.timeout,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            self._client.close()
            self._client = None

    # ── token ─────────────────────────────────────────────────────────────────

    def set_token(self, token: str) -> None:
        self._token = token
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {token}"

    # ── request ───────────────────────────────────────────────────────────────

    def request(self, method: str, path: str, **kwargs) -> Any:
        if self._client is None:
            raise SWException("Client not initialized. Use 'with' context manager.")
        try:
            response = self._client.request(method, path, **kwargs)
            _raise_for_status(response)
            if response.content:
                return response.json()
            return {}
        except SWException:
            raise
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            raise SWConnectionError(f"Connection error: {e}") from e
        except Exception as e:
            raise SWException(f"Unexpected error: {e}") from e

    def get(self, path: str, **kwargs) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Any:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Any:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> Any:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self.request("DELETE", path, **kwargs)


class BaseAsyncClient:
    """Asynchronous HTTP client using httpx.AsyncClient.

    Use as an async context manager:
        async with BaseAsyncClient(api_url) as client:
            data = await client.get("/api/resource")
    """

    def __init__(
        self,
        api_url: str,
        token: Optional[str] = None,
        timeout: int = 30,
        user_agent: str = _DEFAULT_USER_AGENT,
    ):
        self.api_url = api_url.rstrip("/")
        self._token = token
        self.timeout = timeout
        self.user_agent = user_agent
        self._client: Optional[httpx.AsyncClient] = None

    # ── context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> "BaseAsyncClient":
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.AsyncClient(
            base_url=self.api_url,
            headers=headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── token ─────────────────────────────────────────────────────────────────

    def set_token(self, token: str) -> None:
        self._token = token
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {token}"

    # ── request ───────────────────────────────────────────────────────────────

    async def request(self, method: str, path: str, **kwargs) -> Any:
        if self._client is None:
            raise SWException("Client not initialized. Use 'async with' context manager.")
        try:
            response = await self._client.request(method, path, **kwargs)
            _raise_for_status(response)
            if response.content:
                return response.json()
            return {}
        except SWException:
            raise
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            raise SWConnectionError(f"Connection error: {e}") from e
        except Exception as e:
            raise SWException(f"Unexpected error: {e}") from e

    async def get(self, path: str, **kwargs) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> Any:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> Any:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs) -> Any:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> Any:
        return await self.request("DELETE", path, **kwargs)
