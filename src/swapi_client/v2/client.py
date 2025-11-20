import asyncio
from typing import Optional, Dict, Any

import httpx

from .exceptions import SWAPIError, SWAPIAuthError


class SWAPIClient:
    """
    SWAPIClient — async, auto-login, auto-retry po 401.
    
    Funkcje:
    - login() — pozyskanie tokena
    - _request() — jedno miejsce dla GET/POST/PATCH/DELETE
    - auto-refresh tokena przy 401 (bez refresh tokenów — ponowne logowanie)
    - concurrency-safe dzięki asyncio.Lock
    - obsługa JSON + błędów
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        client_id: str,
        auth_token: str,
        timeout: float = 20.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.client_id = client_id
        self.auth_token = auth_token
        self.timeout = timeout

        self.token: Optional[str] = None
        self._login_lock = asyncio.Lock()  # tylko jeden login naraz

    # --------------------------------------------------------
    #  LOGIN
    # --------------------------------------------------------
    async def login(self) -> str:
        """
        Logowanie do SWAPI. Zakładamy endpoint /_/security/login:
        
        POST /_/security/login
        { "username": "...", "password": "..." }
        -> { "token": "..." }

        Dostosuj jeśli endpoint działa inaczej.
        """
        url = f"{self.base_url}/_/security/login"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json={
                "clientId": self.client_id,
                "authToken": self.auth_token,
                "login": self.username,
                "password": self.password,
            })

            if resp.status_code >= 400:
                raise SWAPIAuthError(
                    f"Login failed ({resp.status_code}): {resp.text}"
                )

            data = resp.json()
            token = data.get("token")
            if not token:
                raise SWAPIAuthError("Login response missing 'token' field")

            self.token = token
            return token

    # --------------------------------------------------------
    #  HEADERS
    # --------------------------------------------------------
    async def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    # --------------------------------------------------------
    #  GŁÓWNY REQUEST
    # --------------------------------------------------------
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        - Dodaje base_url
        - Dodaje Authorization
        - Jeśli token jest None → login()
        - Jeśli 401 → retry z loginem
        """
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:

            # 1) Jeśli pierwszy request → login()
            if not self.token:
                async with self._login_lock:
                    if not self.token:  # drugi request czekał na lock
                        await self.login()

            # 2) Pierwsze podejście
            resp = await client.request(
                method,
                url,
                headers=await self._headers(),
                **kwargs
            )

            # 3) Jeśli token wygasł → ponawiamy login
            if resp.status_code == 401:
                async with self._login_lock:
                    await self.login()

                # 4) Retry z nowym tokenem
                resp = await client.request(
                    method,
                    url,
                    headers=await self._headers(),
                    **kwargs
                )

            # 5) Obsługa błędów
            if resp.status_code >= 400:
                raise SWAPIError(
                    f"SWAPI HTTP {resp.status_code} on {method} {url}: {resp.text}"
                )

            # 6) OBSŁUGA JSON
            if not resp.text:
                return {}
            try:
                return resp.json()
            except Exception:
                raise SWAPIError(
                    f"Invalid JSON response from SWAPI: {resp.text}"
                )

    # --------------------------------------------------------
    #  PUBLIC API METHODS
    # --------------------------------------------------------
    async def get(self, endpoint: str, params: dict = None) -> Dict[str, Any]:
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str, json: dict = None) -> Dict[str, Any]:
        return await self._request("POST", endpoint, json=json)

    async def patch(self, endpoint: str, json: dict = None) -> Dict[str, Any]:
        return await self._request("PATCH", endpoint, json=json)

    async def delete(self, endpoint: str, params: dict = None) -> Dict[str, Any]:
        return await self._request("DELETE", endpoint, params=params)