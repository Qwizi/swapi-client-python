import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable

from httpx import AsyncClient, HTTPStatusError

from .exceptions import SWException
from .query_builder import SWQueryBuilder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseSWApiClient:
    """
    Asynchronous client for the Serwis Planner API.

    This client handles HTTP requests to the API, including authentication,
    rate limiting, and error handling. It provides methods for making GET, POST,
    PUT, and DELETE requests.
    """

    def __init__(
        self,
        api_url: str,
        token: Optional[str] = None,
        timeout: int = 30,
        user_agent: str = "SWApiClient/1.0 (Python client)",
    ):
        """
        Initializes the API client.

        Args:
            api_url: The base URL of the Serwis Planner API.
            token: An optional authentication token to use for requests.
            timeout: The request timeout in seconds.
            user_agent: The User-Agent header for requests.
        """
        self.api_url = api_url.rstrip("/")
        self._token = token
        self.timeout = timeout
        self.user_agent = user_agent
        self._client = None

    async def __aenter__(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        self._client = AsyncClient(
            base_url=self.api_url,
            headers=headers,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        query_builder: Optional["SWQueryBuilder"] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Makes an HTTP request to the API.

        Args:
            method: The HTTP method (GET, POST, PUT, DELETE).
            path: The API endpoint path.
            query_builder: An optional SWQueryBuilder instance for query parameters.
            **kwargs: Additional arguments for the httpx request.

        Returns:
            The JSON response as a dictionary.

        Raises:
            SWException: If the API returns an error.
        """
        if self._client is None:
            raise SWException("Client not initialized. Use 'async with' context.")

        if query_builder:
            if "params" not in kwargs:
                kwargs["params"] = {}
            kwargs["params"].update(query_builder.build())

        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            raise SWException(
                f"API request failed: {e.response.status_code} {e.response.text}"
            ) from e
        except Exception as e:
            raise SWException(f"An unexpected error occurred: {e}") from e

    async def get(self, path: str, **kwargs) -> Dict[str, Any]:
        """Performs a GET request."""
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> Dict[str, Any]:
        """Performs a POST request."""
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> Dict[str, Any]:
        """Performs a PUT request."""
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs) -> Dict[str, Any]:
        """Performs a PATCH request."""
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        """Performs a DELETE request."""
        return await self.request("DELETE", path, **kwargs)


class SWApiClient(BaseSWApiClient):
    """
    A specialized Serwis Planner API client.

    This class inherits from the base `BaseSWApiClient` and provides methods
    for interacting with all major endpoints of the Serwis Planner API.
    """

    # =============================================================================
    # AUTHENTICATION
    # =============================================================================
    def set_token(self, token: str):
        """
        Sets the authentication token for subsequent requests and updates the client headers.
        """
        self._token = token
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {self._token}"

    async def login(
        self, clientId: str, authToken: str, login: str, password: str
    ) -> str:
        """
        Performs a login to the /_/security/login endpoint.
        This is typically used for interactive logins, not for API key authentication.
        After a successful login, the token is stored and used for subsequent requests.

        Args:
            clientId: The client ID for login.
            authToken: The auth token for login.
            login: The username.
            password: The password.

        Returns:
            The authentication token string.
        """
        data = {
            "clientId": clientId,
            "authToken": authToken,
            "login": login,
            "password": password,
        }
        response = await self.post("/_/security/login", json=data)
        token = response.get("token")
        if not token:
            raise SWException("Login failed, token not found in response.")

        self.set_token(token)
        return token

    async def verify_token(self) -> Dict[str, Any]:
        """
        Verifies the authentication token by making a test request to the /api/me endpoint.

        Returns:
            The response from the /api/me endpoint if authentication is successful.

        Raises:
            SWException: If authentication fails.
        """
        try:
            return await self.get_me()
        except SWException as e:
            raise SWException(
                "Token verification failed. Please check your token."
            ) from e

    # =============================================================================
    # PAGINATION HELPER
    # =============================================================================

    async def get_all_pages(
        self,
        paginated_method: "Callable[..., Awaitable[Dict[str, Any]]]",
        *args,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all items from a paginated endpoint by automatically handling pagination.

        This helper method repeatedly calls a paginated API method, adjusting the
        page offset until all items have been fetched. It's useful for endpoints
        that return a list of resources spread across multiple pages.

        Args:
            paginated_method: The bound client method to call for each page (e.g., `client.get_products`).
            *args: Positional arguments to pass to the paginated method.
            **kwargs: Keyword arguments to pass to the paginated method.

        Returns:
            A list containing all items from all pages.

        Example:
            # Get all products without worrying about pagination
            all_products = await client.get_all_pages(client.get_products)

            # Get all users for a specific company
            all_users = await client.get_all_pages(
                client.get_account_users,
                query_builder=SWQueryBuilder().filter("companyId", 123)
            )
        """
        all_items = []
        offset = 0
        limit = 100  # Default or a reasonable page size

        query_builder = kwargs.get("query_builder")
        if query_builder is None:
            query_builder = SWQueryBuilder()
            kwargs["query_builder"] = query_builder

        query_builder.page_limit(limit)

        while True:
            query_builder.page_offset(offset)
            response = await paginated_method(*args, **kwargs)
            items = response.get("data", [])
            if not items:
                break
            all_items.extend(items)
            if len(items) < limit:
                break
            offset += limit

        return all_items

    # =============================================================================
    # ACCOUNT COMPANIES ENDPOINTS
    # =============================================================================

    async def get_account_companies_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for account companies, including field information.
        Args:
            query_builder: Optional query builder for filtering and pagination
        Returns:
            Dict: Metadata for account companies
        """
        return await self.get_entity_meta("account_companies", query_builder)

    async def get_account_companies(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get account companies from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Account companies data
        """
        return await self.get("/api/account_companies", query_builder=query_builder)

    async def get_account_company(
        self, company_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific account company by ID

        Args:
            company_id: Company ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Account company data
        """
        return await self.get(
            f"/api/account_companies/{company_id}", query_builder=query_builder
        )

    async def create_account_company(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new account company

        Args:
            data: Company data

        Returns:
            Dict: Created company data
        """
        return await self.post(
            "/api/account_companies",
            json=data,
        )

    async def patch_account_company(
        self, company_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update an account company

        Args:
            company_id: Company ID
            data: Partial company data

        Returns:
            Dict: Updated company data
        """
        return await self.patch(
            f"/api/account_companies/{company_id}",
            json=data,
        )

    async def delete_account_company(self, company_id: int) -> Dict[str, Any]:
        """
        Delete an account company

        Args:
            company_id: Company ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/account_companies/{company_id}")

    async def patch_account_companies(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple account companies based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering companies.
            data: Data to update in the companies.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/account_companies", json=data, query_builder=query_builder
        )

    async def delete_account_companies(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple account companies based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering companies.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/account_companies", query_builder=query_builder)

    async def generate_account_company_pdf(
        self, company_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for an account company.

        Args:
            company_id: The ID of the company to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """

        return await self.get_entity_generate_pdf(
            "account_companies", company_id, template_id
        )

    # =============================================================================
    # ACCOUNT COMPANNY ATTRIBUTES ENDPOINTS
    # =============================================================================

    async def get_account_company_attributes_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for account company attributes, including field information.
        Args:
            query_builder: Optional query builder for filtering and pagination
        Returns:
            Dict: Metadata for account company attributes
        """
        return await self.get_entity_meta("account_company_attributes", query_builder)

    async def get_account_company_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get account company attributes from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Account company attributes data
        """
        return await self.get(
            "/api/account_company_attributes", query_builder=query_builder
        )

    async def get_account_company_attribute(
        self, attribute_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific account company attribute by ID

        Args:
            attribute_id: Attribute ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Account company attribute data
        """
        return await self.get(
            f"/api/account_company_attributes/{attribute_id}",
            query_builder=query_builder,
        )

    async def create_account_company_attribute(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new account company attribute

        Args:
            data: Attribute data

        Returns:
            Dict: Created attribute data
        """
        return await self.post(
            "/api/account_company_attributes",
            json=data,
        )

    async def patch_account_company_attribute(
        self, attribute_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update an account company attribute

        Args:
            attribute_id: Attribute ID
            data: Partial attribute data

        Returns:
            Dict: Updated attribute data
        """
        return await self.patch(
            f"/api/account_company_attributes/{attribute_id}",
            json=data,
        )

    async def delete_account_company_attribute(
        self, attribute_id: int
    ) -> Dict[str, Any]:
        """
        Delete an account company attribute

        Args:
            attribute_id: Attribute ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/account_company_attributes/{attribute_id}")

    async def patch_account_company_attributes(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple account company attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.
            data: Data to update in the attributes.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/account_company_attributes", json=data, query_builder=query_builder
        )

    async def delete_account_company_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple account company attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/account_company_attributes", query_builder=query_builder
        )

    async def generate_account_company_attribute_pdf(
        self, attribute_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for an account company attribute.

        Args:
            attribute_id: The ID of the attribute to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "account_company_attributes", attribute_id, template_id
        )

    # =============================================================================
    # ACCOUNT COMPANY HISTORIES ENDPOINTS
    # =============================================================================

    async def get_account_company_histories_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for account company histories, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for account company histories
        """
        return await self.get_entity_meta("account_company_histories", query_builder)

    async def get_account_company_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get account company histories from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Account company histories data
        """
        return await self.get(
            "/api/account_company_histories", query_builder=query_builder
        )

    async def get_account_company_history(
        self, history_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific account company history by ID

        Args:
            history_id: History ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Account company history data
        """
        return await self.get(
            f"/api/account_company_histories/{history_id}",
            query_builder=query_builder,
        )

    async def create_account_company_history(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new account company history

        Args:
            data: History data

        Returns:
            Dict: Created history data
        """
        return await self.post(
            "/api/account_company_histories",
            json=data,
        )

    async def patch_account_company_history(
        self, history_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update an account company history

        Args:
            history_id: History ID
            data: Partial history data

        Returns:
            Dict: Updated history data
        """
        return await self.patch(
            f"/api/account_company_histories/{history_id}",
            json=data,
        )

    async def delete_account_company_history(self, history_id: int) -> Dict[str, Any]:
        """
        Delete an account company history

        Args:
            history_id: History ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/account_company_histories/{history_id}")

    async def patch_account_company_histories(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple account company histories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering histories.
            data: Data to update in the histories.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/account_company_histories", json=data, query_builder=query_builder
        )

    async def delete_account_company_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple account company histories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering histories.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/account_company_histories", query_builder=query_builder
        )

    async def generate_account_company_history_pdf(
        self, history_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for an account company history.

        Args:
            history_id: The ID of the history to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "account_company_histories", history_id, template_id
        )

    # =============================================================================
    # ACCOUNT USERS ENDPOINTS
    # =============================================================================

    async def get_account_users_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for account users, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for account users
        """
        return await self.get_entity_meta("account_users", query_builder)

    async def get_account_users(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get("/api/account_users", query_builder=query_builder)

    async def get_account_user(
        self, user_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get(
            f"/api/account_users/{user_id}", query_builder=query_builder
        )

    async def create_account_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.post(
            "/api/account_users",
            json=data,
        )

    async def patch_account_user(
        self, user_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self.patch(
            f"/api/account_users/{user_id}",
            json=data,
        )

    async def delete_account_user(self, user_id: int) -> Dict[str, Any]:
        return await self.delete(f"/api/account_users/{user_id}")

    async def patch_account_users(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple account users based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering users.
            data: Data to update in the users.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/account_users", json=data, query_builder=query_builder
        )

    async def delete_account_users(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple account users based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering users.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/account_users", query_builder=query_builder)

    async def generate_account_user_pdf(self, user_id: int, template_id: int = "0"):
        """
        Generate a PDF for an account user.

        Args:
            user_id: The ID of the user to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf("account_users", user_id, template_id)

    # =============================================================================
    # ACCOUNT USER ATTRIBUTES ENDPOINTS
    # =============================================================================

    async def get_account_user_attributes_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for account user attributes, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for account user attributes
        """
        return await self.get_entity_meta("account_user_attributes", query_builder)

    async def get_account_user_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get account user attributes from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Account user attributes data
        """
        return await self.get(
            "/api/account_user_attributes", query_builder=query_builder
        )

    async def get_account_user_attribute(
        self, attribute_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific account user attribute by ID

        Args:
            attribute_id: Attribute ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Account user attribute data
        """
        return await self.get(
            f"/api/account_user_attributes/{attribute_id}",
            query_builder=query_builder,
        )

    async def create_account_user_attribute(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new account user attribute

        Args:
            data: Attribute data

        Returns:
            Dict: Created attribute data
        """
        return await self.post(
            "/api/account_user_attributes",
            json=data,
        )

    async def patch_account_user_attribute(
        self, attribute_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update an account user attribute

        Args:
            attribute_id: Attribute ID
            data: Partial attribute data

        Returns:
            Dict: Updated attribute data
        """
        return await self.patch(
            f"/api/account_user_attributes/{attribute_id}",
            json=data,
        )

    async def delete_account_user_attribute(self, attribute_id: int) -> Dict[str, Any]:
        """
        Delete an account user attribute

        Args:
            attribute_id: Attribute ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/account_user_attributes/{attribute_id}")

    async def patch_account_user_attributes(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple account user attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.
            data: Data to update in the attributes.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/account_user_attributes", json=data, query_builder=query_builder
        )

    async def delete_account_user_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple account user attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/account_user_attributes", query_builder=query_builder
        )

    async def generate_account_user_attribute_pdf(
        self, attribute_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for an account user attribute.

        Args:
            attribute_id: The ID of the attribute to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "account_user_attributes", attribute_id, template_id
        )

    # =============================================================================
    # ACCOUNT USER HISTORIES ENDPOINTS
    # =============================================================================

    async def get_account_user_histories_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for account user histories, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for account user histories
        """
        return await self.get_entity_meta("account_user_histories", query_builder)

    async def get_account_user_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get account user histories from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Account user histories data
        """
        return await self.get(
            "/api/account_user_histories", query_builder=query_builder
        )

    async def get_account_user_history(
        self, history_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific account user history by ID

        Args:
            history_id: History ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Account user history data
        """
        return await self.get(
            f"/api/account_user_histories/{history_id}",
            query_builder=query_builder,
        )

    async def create_account_user_history(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new account user history

        Args:
            data: History data

        Returns:
            Dict: Created history data
        """
        return await self.post(
            "/api/account_user_histories",
            json=data,
        )

    async def patch_account_user_history(
        self, history_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update an account user history

        Args:
            history_id: History ID
            data: Partial history data

        Returns:
            Dict: Updated history data
        """
        return await self.patch(
            f"/api/account_user_histories/{history_id}",
            json=data,
        )

    async def delete_account_user_history(self, history_id: int) -> Dict[str, Any]:
        """
        Delete an account user history

        Args:
            history_id: History ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/account_user_histories/{history_id}")

    async def patch_account_user_histories(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple account user histories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering histories.
            data: Data to update in the histories.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/account_user_histories", json=data, query_builder=query_builder
        )

    async def delete_account_user_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple account user histories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering histories.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/account_user_histories", query_builder=query_builder
        )

    async def generate_account_user_history_pdf(
        self, history_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for an account user history.

        Args:
            history_id: The ID of the history to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "account_user_histories", history_id, template_id
        )

    # =============================================================================
    # USER PROFILE ENDPOINTS
    # =============================================================================
    async def get_user_profiles_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for user profiles, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for user profiles
        """
        return await self.get_entity_meta("user_profiles", query_builder)

    async def get_user_profiles(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get user profiles from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: User profiles data
        """
        return await self.get("/api/user_profiles", query_builder=query_builder)

    async def get_user_profile(
        self, profile_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific user profile by ID

        Args:
            profile_id: Profile ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: User profile data
        """
        return await self.get(
            f"/api/user_profiles/{profile_id}", query_builder=query_builder
        )

    async def create_user_profile(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user profile

        Args:
            data: Profile data

        Returns:
            Dict: Created profile data
        """
        return await self.post(
            "/api/user_profiles",
            json=data,
        )

    async def patch_user_profile(
        self, profile_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a user profile

        Args:
            profile_id: Profile ID
            data: Partial profile data

        Returns:
            Dict: Updated profile data
        """
        return await self.patch(
            f"/api/user_profiles/{profile_id}",
            json=data,
        )

    async def delete_user_profile(self, profile_id: int) -> Dict[str, Any]:
        """
        Delete a user profile

        Args:
            profile_id: Profile ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/user_profiles/{profile_id}")

    async def patch_user_profiles(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple user profiles based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering profiles.
            data: Data to update in the profiles.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/user_profiles", json=data, query_builder=query_builder
        )

    async def delete_user_profiles(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple user profiles based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering profiles.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/user_profiles", query_builder=query_builder)

    async def generate_user_profile_pdf(self, profile_id: int, template_id: int = "0"):
        """
        Generate a PDF for a user profile.

        Args:
            profile_id: The ID of the profile to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "user_profiles", profile_id, template_id
        )

    # =============================================================================
    # ADDITIONAL I18NS ENDPOINTS
    # =============================================================================
    async def get_additional_i18ns(
        self, module: str, query_builder: Optional["SWQueryBuilder"] = None
    ):
        """
        Get additional i18n data for a specific module.

        Args:
            module: The module name to fetch i18n data for.
            query_builder: Optional query builder for filtering and pagination.

        Returns:
            Dict: Additional i18n data for the specified module.
        """
        return await self.get(
            f"/api/additional_i18ns/{module}", query_builder=query_builder
        )

    # =============================================================================
    # BASKED ENDPOINTS !!TODO!!
    # =============================================================================

    # =============================================================================
    # CAMPAIGNS ENDPOINTS !!TODO!!
    # =============================================================================

    # =============================================================================
    # COMMISSIONS ENDPOINTS
    # =============================================================================

    async def get_commissions(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commissions from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commissions data
        """
        return await self.get("/api/commissions", query_builder=query_builder)

    async def get_commission(
        self, commission_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission by ID

        Args:
            commission_id: Commission ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission data
        """
        return await self.get(
            f"/api/commissions/{commission_id}", query_builder=query_builder
        )

    async def create_commission(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new commission

        Args:
            data: Commission data

        Returns:
            Dict: Created commission data
        """
        return await self.post("/api/commissions", json=data)

    async def patch_commission(
        self, commission_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a commission

        Args:
            commission_id: Commission ID
            data: Updated commission data

        Returns:
            Dict: Updated commission data
        """
        return await self.patch(
            f"/api/commissions/{commission_id}",
            json=data,
        )

    async def delete_commission(self, commission_id: int) -> Dict[str, Any]:
        """
        Delete a commission

        Args:
            commission_id: Commission ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commissions/{commission_id}")

    async def patch_commissions(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = {},
    ) -> Dict[str, Any]:
        """
        Partially update commissions based on a query builder.

        Args:
            query_builder: Optional query builder for filtering commissions.
            data: Data to update in the commissions.

        Returns:
            Dict: Updated commissions data.
        """
        return await self.patch(
            "/api/commissions",
            json=data,
            query_builder=query_builder,
        )

    async def delete_commissions(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete commissions based on a query builder.

        Args:
            query_builder: Optional query builder for filtering commissions.

        Returns:
            Dict: Deletion result.
        """
        return await self.delete(
            "/api/commissions",
            query_builder=query_builder,
        )

    async def generate_commission_pdf(self, commission_id: int, template_id: int = "0"):
        """
        Generate a PDF for a commission.

        Args:
            commission_id: The ID of the commission to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commissions", commission_id, template_id
        )

    # =============================================================================
    # COMMISSION ATTRIBUTES ENDPOINTS
    # =============================================================================

    async def get_commission_attributes_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission attributes, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission attributes
        """
        return await self.get_entity_meta("commission_attributes", query_builder)

    async def get_commission_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission attributes from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission attributes data
        """
        return await self.get("/api/commission_attributes", query_builder=query_builder)

    async def get_commission_attribute(
        self, attribute_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission attribute by ID

        Args:
            attribute_id: Attribute ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission attribute data
        """
        return await self.get(
            f"/api/commission_attributes/{attribute_id}",
            query_builder=query_builder,
        )

    async def create_commission_attribute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new commission attribute

        Args:
            data: Attribute data

        Returns:
            Dict: Created attribute data
        """
        return await self.post(
            "/api/commission_attributes",
            json=data,
        )

    async def patch_commission_attribute(
        self, attribute_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commission attribute

        Args:
            attribute_id: Attribute ID
            data: Partial attribute data

        Returns:
            Dict: Updated attribute data
        """
        return await self.patch(
            f"/api/commission_attributes/{attribute_id}",
            json=data,
        )

    async def delete_commission_attribute(self, attribute_id: int) -> Dict[str, Any]:
        """
        Delete a commission attribute

        Args:
            attribute_id: Attribute ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commission_attributes/{attribute_id}")

    async def patch_commission_attributes(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commission attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.
            data: Data to update in the attributes.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commission_attributes", json=data, query_builder=query_builder
        )

    async def delete_commission_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commission attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/commission_attributes", query_builder=query_builder
        )

    async def generate_commission_attribute_pdf(
        self, attribute_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a commission attribute.

        Args:
            attribute_id: The ID of the attribute to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commission_attributes", attribute_id, template_id
        )

    # =============================================================================
    # COMMISSION ATTRIBUTE CRITERIAS ENDPOINTS
    # =============================================================================

    async def get_commission_attribute_criteria_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission attribute criteria, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission attribute criteria
        """
        return await self.get_entity_meta(
            "commission_attribute_criterias", query_builder
        )

    async def get_commission_attribute_criterias(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission attribute criterias from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission attribute criterias data
        """
        return await self.get(
            "/api/commission_attribute_criterias", query_builder=query_builder
        )

    async def get_commission_attribute_criteria(
        self, criteria_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission attribute criteria by ID

        Args:
            criteria_id: Criteria ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission attribute criteria data
        """
        return await self.get(
            f"/api/commission_attribute_criterias/{criteria_id}",
            query_builder=query_builder,
        )

    async def create_commission_attribute_criteria(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new commission attribute criteria

        Args:
            data: Criteria data

        Returns:
            Dict: Created criteria data
        """
        return await self.post(
            "/api/commission_attribute_criterias",
            json=data,
        )

    async def patch_commission_attribute_criteria(
        self, criteria_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commission attribute criteria

        Args:
            criteria_id: Criteria ID
            data: Partial criteria data

        Returns:
            Dict: Updated criteria data
        """
        return await self.patch(
            f"/api/commission_attribute_criterias/{criteria_id}",
            json=data,
        )

    async def delete_commission_attribute_criteria(
        self, criteria_id: int
    ) -> Dict[str, Any]:
        """
        Delete a commission attribute criteria

        Args:
            criteria_id: Criteria ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commission_attribute_criterias/{criteria_id}")

    async def patch_commission_attribute_criterias(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commission attribute criterias based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering criterias.
            data: Data to update in the criterias.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commission_attribute_criterias",
            json=data,
            query_builder=query_builder,
        )

    async def delete_commission_attribute_criterias(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commission attribute criterias based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering criterias.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/commission_attribute_criterias", query_builder=query_builder
        )

    async def generate_commission_attribute_criteria_pdf(
        self, criteria_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a commission attribute criteria.

        Args:
            criteria_id: The ID of the criteria to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commission_attribute_criterias", criteria_id, template_id
        )

    # =============================================================================
    # COMMISSION ATTRIBUTE RELATIONS ENDPOINTS
    # =============================================================================
    async def get_commission_attribute_relations_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission attribute relations, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission attribute relations
        """
        return await self.get_entity_meta(
            "commission_attribute_relations", query_builder
        )

    async def get_commission_attribute_relations(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission attribute relations from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission attribute relations data
        """
        return await self.get(
            "/api/commission_attribute_relations", query_builder=query_builder
        )

    async def get_commission_attribute_relation(
        self, relation_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission attribute relation by ID

        Args:
            relation_id: Relation ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission attribute relation data
        """
        return await self.get(
            f"/api/commission_attribute_relations/{relation_id}",
            query_builder=query_builder,
        )

    async def create_commission_attribute_relation(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new commission attribute relation

        Args:
            data: Relation data

        Returns:
            Dict: Created relation data
        """
        return await self.post(
            "/api/commission_attribute_relations",
            json=data,
        )

    async def patch_commission_attribute_relation(
        self, relation_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commission attribute relation

        Args:
            relation_id: Relation ID
            data: Partial relation data

        Returns:
            Dict: Updated relation data
        """
        return await self.patch(
            f"/api/commission_attribute_relations/{relation_id}",
            json=data,
        )

    async def delete_commission_attribute_relation(
        self, relation_id: int
    ) -> Dict[str, Any]:
        """
        Delete a commission attribute relation

        Args:
            relation_id: Relation ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commission_attribute_relations/{relation_id}")

    async def patch_commission_attribute_relations(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commission attribute relations based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering relations.
            data: Data to update in the relations.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commission_attribute_relations",
            json=data,
            query_builder=query_builder,
        )

    async def delete_commission_attribute_relations(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commission attribute relations based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering relations.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/commission_attribute_relations", query_builder=query_builder
        )

    async def generate_commission_attribute_relation_pdf(
        self, relation_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a commission attribute relation.

        Args:
            relation_id: The ID of the relation to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commission_attribute_relations", relation_id, template_id
        )
    
    # =============================================================================
    # COMMISSION ATTRIBUTE RELATIONS ACTIONS ENDPOINTS
    # =============================================================================
    async def get_commission_attribute_relation_actions_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission attribute relation actions, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission attribute relation actions
        """
        return await self.get_entity_meta(
            "commission_attribute_relation_actions", query_builder
        )
    
    async def get_commission_attribute_relation_actions(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission attribute relation actions from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission attribute relation actions data
        """
        return await self.get(
            "/api/commission_attribute_relation_actions", query_builder=query_builder
        )
    
    async def get_commission_attribute_relation_action(
        self, action_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission attribute relation action by ID

        Args:
            action_id: Action ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission attribute relation action data
        """
        return await self.get(
            f"/api/commission_attribute_relation_actions/{action_id}",
            query_builder=query_builder,
        )
    
    async def create_commission_attribute_relation_action(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new commission attribute relation action

        Args:
            data: Action data

        Returns:
            Dict: Created action data
        """
        return await self.post(
            "/api/commission_attribute_relation_actions",
            json=data,
        )
    
    async def patch_commission_attribute_relation_action(
        self, action_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commission attribute relation action

        Args:
            action_id: Action ID
            data: Partial action data

        Returns:
            Dict: Updated action data
        """
        return await self.patch(
            f"/api/commission_attribute_relation_actions/{action_id}",
            json=data,
        )
    
    async def delete_commission_attribute_relation_action(
        self, action_id: int
    ) -> Dict[str, Any]:
        """
        Delete a commission attribute relation action

        Args:
            action_id: Action ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commission_attribute_relation_actions/{action_id}")
    
    async def patch_commission_attribute_relation_actions(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commission attribute relation actions based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering actions.
            data: Data to update in the actions.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commission_attribute_relation_actions",
            json=data,
            query_builder=query_builder,
        )
    
    async def delete_commission_attribute_relation_actions(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commission attribute relation actions based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering actions.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/commission_attribute_relation_actions", query_builder=query_builder
        )
    
    async def generate_commission_attribute_relation_action_pdf(
        self, action_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a commission attribute relation action.

        Args:
            action_id: The ID of the action to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commission_attribute_relation_actions", action_id, template_id
        )
    
    # =============================================================================
    # COMMISSION HISTORIES ENDPOINTS
    # =============================================================================

    async def get_commission_histories_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission histories, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission histories
        """
        return await self.get_entity_meta("commission_histories", query_builder)
    
    async def get_commission_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission histories from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission histories data
        """
        return await self.get("/api/commission_histories", query_builder=query_builder)
    
    async def get_commission_history(
        self, history_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission history by ID

        Args:
            history_id: History ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission history data
        """
        return await self.get(
            f"/api/commission_histories/{history_id}",
            query_builder=query_builder,
        )
    async def create_commission_history(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new commission history

        Args:
            data: History data

        Returns:
            Dict: Created history data
        """
        return await self.post(
            "/api/commission_histories",
            json=data,
        )
    async def patch_commission_history(
        self, history_id: int, data
: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commission history

        Args:
            history_id: History ID
            data: Partial history data

        Returns:
            Dict: Updated history data
        """
        return await self.patch(
            f"/api/commission_histories/{history_id}",
            json=data,
        )
    
    async def delete_commission_history(self, history_id: int) -> Dict[str, Any]:
        """
        Delete a commission history

        Args:
            history_id: History ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commission_histories/{history_id}")
    

    async def patch_commission_histories(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commission histories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering histories.
            data: Data to update in the histories.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commission_histories", json=data, query_builder=query_builder
        )
    
    async def delete_commission_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commission histories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering histories.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/commission_histories", query_builder=query_builder
        )
    
    async def generate_commission_history_pdf(
        self, history_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a commission history.

        Args:
            history_id: The ID of the history to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commission_histories", history_id, template_id
        )
    
    # =============================================================================
    # COMMISSION PHASES ENDPOINTS
    # =============================================================================

    async def get_commission_phases_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission phases, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission phases
        """
        return await self.get_entity_meta("commission_phases", query_builder)
    
    async def get_commission_phases(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission phases from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission phases data
        """
        return await self.get("/api/commission_phases", query_builder=query_builder)
    

    async def get_commission_phase(
        self, phase_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission phase by ID

        Args:
            phase_id: Phase ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission phase data
        """
        return await self.get(
            f"/api/commission_phases/{phase_id}",
            query_builder=query_builder,
        )
    
    async def create_commission_phase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new commission phase

        Args:
            data: Phase data

        Returns:
            Dict: Created phase data
        """
        return await self.post(
            "/api/commission_phases",
            json=data,
        )
    
    async def patch_commission_phase(
        self, phase_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commission phase

        Args:
            phase_id: Phase ID
            data: Partial phase data

        Returns:
            Dict: Updated phase data
        """
        return await self.patch(
            f"/api/commission_phases/{phase_id}",
            json=data,
        )
    
    async def delete_commission_phase(self, phase_id: int) -> Dict[str, Any]:
        """
        Delete a commission phase

        Args:
            phase_id: Phase ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commission_phases/{phase_id}")
    
    async def patch_commission_phases(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commission phases based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering phases.
            data: Data to update in the phases.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commission_phases", json=data, query_builder=query_builder
        )
    
    async def delete_commission_phases(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commission phases based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering phases.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/commission_phases", query_builder=query_builder
        )
    
    async def generate_commission_phase_pdf(
        self, phase_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a commission phase.

        Args:
            phase_id: The ID of the phase to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commission_phases", phase_id, template_id
        )
    

    # =============================================================================
    # COMMISSION SCOPE TYPE ENDPOINTS
    # =============================================================================
    async def get_commission_scope_types_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission scope types, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission scope types
        """
        return await self.get_entity_meta("commission_scope_types", query_builder)
    
    async def get_commission_scope_types(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission scope types from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission scope types data
        """
        return await self.get("/api/commission_scope_types", query_builder=query_builder)
    
    async def get_commission_scope_type(
        self, scope_type_id: int, query_builder: Optional["SWQueryBuilder"] =
            None
    ) -> Dict[str, Any]:
        """
        Get a specific commission scope type by ID

        Args:
            scope_type_id: Scope type ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission scope type data
        """
        return await self.get(
            f"/api/commission_scope_types/{scope_type_id}",
            query_builder=query_builder,
        )
    
    async def create_commission_scope_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new commission scope type

        Args:
            data: Scope type data

        Returns:
            Dict: Created scope type data
        """
        return await self.post(
            "/api/commission_scope_types",
            json=data,
        )
    
    async def patch_commission_scope_type(
        self, scope_type_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commission scope type

        Args:
            scope_type_id: Scope type ID
            data: Partial scope type data

        Returns:
            Dict: Updated scope type data
        """
        return await self.patch(
            f"/api/commission_scope_types/{scope_type_id}",
            json=data,
        )
    async def delete_commission_scope_type(self, scope_type_id: int) -> Dict[str, Any]:
        """
        Delete a commission scope type

        Args:
            scope_type_id: Scope type ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commission_scope_types/{scope_type_id}")

    async def patch_commission_scope_types(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commission scope types based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering scope types.
            data: Data to update in the scope types.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commission_scope_types", json=data, query_builder=query_builder
        )
    
    async def delete_commission_scope_types(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commission scope types based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering scope types.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/commission_scope_types", query_builder=query_builder
        )
    
    async def generate_commission_scope_type_pdf(
        self, scope_type_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a commission scope type.

        Args:
            scope_type_id: The ID of the scope type to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commission_scope_types", scope_type_id, template_id
        )
    

    # =============================================================================
    # PRODUCTS ENDPOINTS
    # =============================================================================

    async def get_products(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get("/api/products", query_builder=query_builder)

    async def get_product(
        self, product_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get(
            f"/api/products/{product_id}", query_builder=query_builder
        )

    async def create_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.post("/api/products", json=data)

    async def update_product(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self.put(
            f"/api/products/{product_id}",
            json=data,
        )

    async def patch_product(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self.patch(
            f"/api/products/{product_id}",
            json=data,
        )

    async def delete_product(self, product_id: int) -> Dict[str, Any]:
        return await self.delete(f"/api/products/{product_id}")

    # =============================================================================
    # SERVICED PRODUCTS ENDPOINTS
    # =============================================================================

    async def get_serviced_products(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get("/api/serviced_products", query_builder=query_builder)

    async def get_serviced_product(
        self, product_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get(
            f"/api/serviced_products/{product_id}", query_builder=query_builder
        )

    async def create_serviced_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.post(
            "/api/serviced_products",
            json=data,
        )

    async def update_serviced_product(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self.put(
            f"/api/serviced_products/{product_id}",
            json=data,
        )

    async def patch_serviced_product(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self.patch(
            f"/api/serviced_products/{product_id}",
            json=data,
        )

    async def delete_serviced_product(self, product_id: int) -> Dict[str, Any]:
        return await self.delete(f"/api/serviced_products/{product_id}")

    # =============================================================================
    # UTILITY AND CORE ENDPOINTS
    # =============================================================================

    async def get_me(self) -> Dict[str, Any]:
        return await self.get("/api/me")

    # =============================================================================
    # UTILITY AND CORE ENDPOINTS (Continued)
    # =============================================================================

    async def upload_file(self, files: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload a file.
        The `files` parameter should be a dictionary suitable for httpx's `files` argument,
        e.g., {'file': ('filename.jpg', open('filename.jpg', 'rb'), 'image/jpeg')}
        """
        # httpx handles multipart/form-data automatically when `files` is passed.
        return await self.post("/api/files/upload", files=files)

    async def upload_files_from_urls(self, urls: List[str]) -> Dict[str, Any]:
        return await self.post("/api/files/upload/urls", json={"data_files_urls": urls})

    # =============================================================================
    # GENERIC HELPERS for Autoselect, Meta, History, Audit, PDF Generation
    # =============================================================================

    async def get_entity_autoselect(
        self, module: str, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Generic helper to get autoselect data for a module."""
        return await self.get(f"/api/{module}/autoselect", query_builder=query_builder)

    async def get_entity_meta(
        self, module: str, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Generic helper to get metadata for a module."""
        return await self.get(f"/api/{module}/meta", query_builder=query_builder)

    async def get_entity_history(
        self, module: str, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Generic helper to get history for a module."""
        # Note: SW API uses both plural (products) and singular_histories (product_histories)
        history_module = f"{module.rstrip('s')}_histories"
        return await self.get(f"/api/{history_module}", query_builder=query_builder)

    async def get_entity_audit(
        self, module: str, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Generic helper to get audit trail for a module."""
        return await self.get(f"/api/audits/{module}", query_builder=query_builder)

    async def get_entity_generate_pdf(
        self,
        module: str,
        item_id: int,
        template_id: int = 0,
    ) -> Dict[str, Any]:
        """
        Generic helper to generate a PDF for a specific item in a module.

        Args:
            module: The name of the module (e.g., 'invoices').
            item_id: The ID of the item.

        Returns:
            A dictionary containing the result of the PDF generation.
        """
        data = {
            "data": {
                "templateId": template_id  # Default template ID, can be changed if needed
            }
        }
        return await self.post(
            f"/api/{module}/{item_id}/generate/pdf",
            json=data,
        )

    # =============================================================================
    # AUTOSELECT ENDPOINTS (for UI dropdowns/selections)
    # =============================================================================

    async def get_account_companies_autoselect(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_autoselect("account_companies", query_builder)

    async def get_account_users_autoselect(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_autoselect("account_users", query_builder)

    async def get_products_autoselect(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_autoselect("products", query_builder)

    async def get_serviced_products_autoselect(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_autoselect("serviced_products", query_builder)

    async def get_baskets_autoselect(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_autoselect("baskets", query_builder)

    async def get_custom_serviced_products_autoselect(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_autoselect(
            "custom_serviced_products", query_builder
        )

    # =============================================================================
    # METADATA ENDPOINTS (for getting field information)
    # =============================================================================

    async def get_account_users_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_meta("account_users", query_builder)

    async def get_products_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_meta("products", query_builder)

    async def get_serviced_products_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_meta("serviced_products", query_builder)

    async def get_commissions_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        return await self.get_entity_meta("commissions", query_builder)

    # =============================================================================
    # SPECIALIZED ENDPOINTS (Reports, Email, PDF Generation, etc.)
    # =============================================================================

    async def get_odbc_reports(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a list of ODBC reports.

        Args:
            query_builder: Optional query builder for filtering and pagination.

        Returns:
            A dictionary containing the list of ODBC reports.
        """
        return await self.get("/api/odbc/reports", query_builder=query_builder)

    async def get_odbc_report(
        self, report_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific ODBC report by ID.

        Args:
            report_id: The ID of the report.
            query_builder: Optional query builder.

        Returns:
            A dictionary containing the report data.
        """
        return await self.get(
            f"/api/odbc/reports/{report_id}", query_builder=query_builder
        )

    async def get_email_messages(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a list of email messages.

        Args:
            query_builder: Optional query builder for filtering and pagination.

        Returns:
            A dictionary containing the list of email messages.
        """
        return await self.get("/api/emails", query_builder=query_builder)

    async def generate_pdf(
        self, module: str, item_id: int, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a PDF for a specific item in a module.

        Args:
            module: The name of the module (e.g., 'invoices').
            item_id: The ID of the item.
            data: Optional data payload for the PDF generation.

        Returns:
            A dictionary containing the result of the PDF generation.
        """
        return await self.post(f"/api/{module}/{item_id}/pdf", json=data)

    # =============================================================================
    # HISTORY AND AUDIT ENDPOINTS
    # =============================================================================

    async def get_account_company_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get history for account companies."""
        return await self.get_entity_history("account_companies", query_builder)

    async def get_account_user_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get history for account users."""
        return await self.get_entity_history("account_users", query_builder)

    async def get_product_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get history for products."""
        return await self.get_entity_history("products", query_builder)

    async def get_serviced_product_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get history for serviced products."""
        return await self.get_entity_history("serviced_products", query_builder)

    async def get_basket_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get history for baskets."""
        return await self.get_entity_history("baskets", query_builder)

    async def get_basket_position_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get history for basket positions."""
        return await self.get_entity_history("basket_positions", query_builder)

    async def get_custom_serviced_product_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get history for custom serviced products."""
        return await self.get_entity_history("custom_serviced_products", query_builder)

    async def get_account_company_audits(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get audit trail for account companies."""
        return await self.get_entity_audit("account_companies", query_builder)

    async def get_account_user_audits(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get audit trail for account users."""
        return await self.get_entity_audit("account_users", query_builder)

    async def get_product_audits(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get audit trail for products."""
        return await self.get_entity_audit("products", query_builder)

    async def get_serviced_product_audits(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get audit trail for serviced products."""
        return await self.get_entity_audit("serviced_products", query_builder)

    async def get_basket_audits(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get audit trail for baskets."""
        return await self.get_entity_audit("baskets", query_builder)

    async def get_basket_position_audits(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get audit trail for basket positions."""
        return await self.get_entity_audit("basket_positions", query_builder)

    async def get_custom_serviced_product_audits(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """Get audit trail for custom serviced products."""
        return await self.get_entity_audit("custom_serviced_products", query_builder)

    # =============================================================================
    # BULK, CONTEXTUAL, AND SEARCH ENDPOINTS
    # =============================================================================

    async def bulk_create(
        self, module: str, data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Bulk create items in a module.

        Args:
            module: The name of the module (e.g., 'products').
            data: A list of dictionaries, each representing an item to create.

        Returns:
            The result of the bulk creation operation.
        """
        return await self.post(f"/api/{module}/bulk", json={"data": data})

    async def bulk_update(
        self, module: str, data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Bulk update items in a module.

        Args:
            module: The name of the module (e.g., 'products').
            data: A list of dictionaries, each representing an item to update.

        Returns:
            The result of the bulk update operation.
        """
        return await self.put(f"/api/{module}/bulk", json={"data": data})

    async def bulk_delete(self, module: str, ids: List[int]) -> Dict[str, Any]:
        """
        Bulk delete items in a module by their IDs.

        Args:
            module: The name of the module (e.g., 'products').
            ids: A list of item IDs to delete.

        Returns:
            The result of the bulk delete operation.
        """
        params = {"ids": ",".join(map(str, ids))}
        return await self.delete(f"/api/{module}/bulk", params=params)

    async def contextual_create(
        self, module: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Contextual create an item in a module.

        Args:
            module: The name of the module.
            data: The data for the new item.

        Returns:
            The created item.
        """
        return await self.post(f"/api/{module}/contextual", json=data)

    async def contextual_update(
        self, module: str, item_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Contextual update an item in a module.

        Args:
            module: The name of the module.
            item_id: The ID of the item to update.
            data: The data to update.

        Returns:
            The updated item.
        """
        return await self.put(f"/api/{module}/{item_id}/contextual", json=data)

    async def contextual_delete(self, module: str, item_id: int) -> Dict[str, Any]:
        """
        Contextual delete an item in a module.

        Args:
            module: The name of the module.
            item_id: The ID of the item to delete.

        Returns:
            The result of the deletion.
        """
        return await self.delete(f"/api/{module}/{item_id}/contextual")

    async def search(
        self, query: str, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Perform a global search across all relevant modules.

        Args:
            query: The search term.
            query_builder: Optional query builder for additional filters.

        Returns:
            A dictionary with search results.
        """
        params = {"query": query}
        if query_builder:
            params.update(query_builder.build())
        return await self.get("/api/search", params=params)
