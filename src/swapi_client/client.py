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

    async def gus_update_account_company(
        self,
        company_id: int,
        data: Dict[str, Any],
        query_builder: Optional["SWQueryBuilder"] = None,
    ) -> Dict[str, Any]:
        """
        Update GUS data.
        Args:
            data: Data to update in GUS
            query_builder: Optional query builder for filtering
        Returns:
            Dict: Result of the GUS update operation
        """
        return await self.patch(
            "/api/account_companies/{company_id}/gusUpdate",
            json=data,
            query_builder=query_builder,
        )

    async def get_odbc_reports_account_companies(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get ODBC reports for account companies.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: ODBC reports data for account companies
        """
        return await self.get(
            "/api/account_companies/odbc_reports", query_builder=query_builder
        )

    async def get_odbc_report_account_company(
        self,
        company_id: int,
        report_id: int,
        query_builder: Optional["SWQueryBuilder"] = None,
    ) -> Dict[str, Any]:
        """
        Get a specific ODBC report for an account company by ID.

        Args:
            company_id: Company ID
            report_id: Report ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: ODBC report data for the account company
        """
        return await self.get(
            f"/api/account_companies/{company_id}/odbc_reports/{report_id}",
            query_builder=query_builder,
        )

    async def get_email_messages_account_company(
        self, company_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get email messages for an account company.

        Args:
            company_id: Company ID
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Email messages data for the account company
        """
        return await self.get(
            f"/api/account_companies/{company_id}/oemail_messages",
            query_builder=query_builder,
        )

    async def get_my_account_company(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get the account company associated with the authenticated user.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Account company data for the authenticated user
        """
        return await self.get(
            "/api/account_companies/myCompany", query_builder=query_builder
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
        return await self.delete(
            f"/api/commission_attribute_relation_actions/{action_id}"
        )

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
        self, history_id: int, data: Dict[str, Any]
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
        return await self.delete("/api/commission_phases", query_builder=query_builder)

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
        return await self.get(
            "/api/commission_scope_types", query_builder=query_builder
        )

    async def get_commission_scope_type(
        self, scope_type_id: int, query_builder: Optional["SWQueryBuilder"] = None
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

    async def create_commission_scope_type(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
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
    # COMMISSION SHORTCUTS ENDPOINTS
    # =============================================================================

    async def get_commission_shortcuts_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission shortcuts, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission shortcuts
        """
        return await self.get_entity_meta("commission_shortcuts", query_builder)

    async def get_commission_shortcuts(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission shortcuts from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission shortcuts data
        """
        return await self.get("/api/commission_shortcuts", query_builder=query_builder)

    async def get_commission_shortcut(
        self, shortcut_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission shortcut by ID

        Args:
            shortcut_id: Shortcut ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission shortcut data
        """
        return await self.get(
            f"/api/commission_shortcuts/{shortcut_id}",
            query_builder=query_builder,
        )

    # ==============================================================================
    # COMMISSION Templates ENDPOINTS
    # ==============================================================================

    async def get_commission_templates_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission templates, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission templates
        """
        return await self.get_entity_meta("commission_templates", query_builder)

    async def get_commission_templates(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission templates from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission templates data
        """
        return await self.get("/api/commission_templates", query_builder=query_builder)

    async def get_commission_template(
        self, template_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission template by ID

        Args:
            template_id: Template ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission template data
        """
        return await self.get(
            f"/api/commission_templates/{template_id}",
            query_builder=query_builder,
        )

    async def create_commission_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new commission template

        Args:
            data: Template data

        Returns:
            Dict: Created template data
        """
        return await self.post(
            "/api/commission_templates",
            json=data,
        )

    async def patch_commission_template(
        self, template_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commission template

        Args:
            template_id: Template ID
            data: Partial template data

        Returns:
            Dict: Updated template data
        """
        return await self.patch(
            f"/api/commission_templates/{template_id}",
            json=data,
        )

    async def delete_commission_template(self, template_id: int) -> Dict[str, Any]:
        """
        Delete a commission template

        Args:
            template_id: Template ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commission_templates/{template_id}")

    async def patch_commission_templates(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commission templates based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering templates.
            data: Data to update in the templates.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commission_templates", json=data, query_builder=query_builder
        )

    async def delete_commission_templates(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commission templates based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering templates.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/commission_templates", query_builder=query_builder
        )

    # !!TODO!!
    # async def generate_commission_template_pdf()

    # =============================================================================
    # COMMISSION USER USERS ENDPOINTS
    # =============================================================================
    async def get_commission_user_users_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commission user users, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commission user users
        """
        return await self.get_entity_meta("commission_user_userss", query_builder)

    async def get_commission_user_users(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commission user users from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commission user users data
        """
        return await self.get(
            "/api/commission_user_userss", query_builder=query_builder
        )

    async def get_commission_user_user(
        self, user_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commission user user by ID

        Args:
            user_id: User ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commission user user data
        """
        return await self.get(
            f"/api/commission_user_userss/{user_id}",
            query_builder=query_builder,
        )

    async def create_commission_user_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new commission user user

        Args:
            data: User data

        Returns:
            Dict: Created user data
        """
        return await self.post(
            "/api/commission_user_userss",
            json=data,
        )

    async def patch_commission_user_user(
        self, user_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commission user user

        Args:
            user_id: User ID
            data: Partial user data

        Returns:
            Dict: Updated user data
        """
        return await self.patch(
            f"/api/commission_user_userss/{user_id}",
            json=data,
        )

    async def delete_commission_user_user(self, user_id: int) -> Dict[str, Any]:
        """
        Delete a commission user user

        Args:
            user_id: User ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commission_user_userss/{user_id}")

    async def patch_commission_user_users(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commission user users based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering users.
            data: Data to update in the users.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commission_user_userss", json=data, query_builder=query_builder
        )

    async def delete_commission_user_users(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commission user users based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering users.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/commission_user_userss", query_builder=query_builder
        )

    async def generate_commission_user_user_pdf(
        self, user_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a commission user user.

        Args:
            user_id: The ID of the user to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commission_user_userss", user_id, template_id
        )

    # =============================================================================
    # KANBANS ENDPOINTS
    # =============================================================================
    async def get_kanbans_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for kanbans, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for kanbans
        """
        return await self.get_entity_meta("kanbans", query_builder)

    async def get_kanbans(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get kanbans from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Kanbans data
        """
        return await self.get("/api/kanbans", query_builder=query_builder)

    async def get_kanban(
        self, kanban_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific kanban by ID

        Args:
            kanban_id: Kanban ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Kanban data
        """
        return await self.get(
            f"/api/kanbans/{kanban_id}",
            query_builder=query_builder,
        )

    async def create_kanban(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new kanban

        Args:
            data: Kanban data

        Returns:
            Dict: Created kanban data
        """
        return await self.post(
            "/api/kanbans",
            json=data,
        )

    async def patch_kanban(
        self, kanban_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a kanban

        Args:
            kanban_id: Kanban ID
            data: Partial kanban data

        Returns:
            Dict: Updated kanban data
        """
        return await self.patch(
            f"/api/kanbans/{kanban_id}",
            json=data,
        )

    async def delete_kanban(self, kanban_id: int) -> Dict[str, Any]:
        """
        Delete a kanban

        Args:
            kanban_id: Kanban ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/kanbans/{kanban_id}")

    async def patch_kanbans(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple kanbans based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering kanbans.
            data: Data to update in the kanbans.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch("/api/kanbans", json=data, query_builder=query_builder)

    async def delete_kanbans(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple kanbans based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering kanbans.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/kanbans", query_builder=query_builder)

    async def generate_kanban_pdf(self, kanban_id: int, template_id: int = "0"):
        """
        Generate a PDF for a kanban.

        Args:
            kanban_id: The ID of the kanban to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf("kanbans", kanban_id, template_id)

    # =============================================================================
    # DOCUMENTS ENDPOINTS !!TODO!!
    # =============================================================================

    # =============================================================================
    # EMAIL MESSAGES ENDPOINTS !!TODO!!
    # =============================================================================

    # =============================================================================
    # FILES ENDPOINTS
    # =============================================================================

    async def delete_file(self, file_id: int) -> Dict[str, Any]:
        """
        Delete a file by its ID.

        Args:
            file_id: The ID of the file to delete.

        Returns:
            Dict: Result of the deletion operation.
        """
        return await self.delete(f"/api/files/{file_id}")

    async def patch_file(self, file_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially update a file's metadata.

        Args:
            file_id: The ID of the file to update.
            data: The data to update in the file's metadata.

        Returns:
            Dict: Updated file metadata.
        """
        return await self.patch(
            f"/api/files/{file_id}",
            json=data,
        )

    async def create_file(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new file entry.

        Args:
            data: The data for the new file.

        Returns:
            Dict: Created file metadata.
        """
        return await self.post("/api/files", json=data)

    async def patch_files(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple files based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering files.
            data: Data to update in the files.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch("/api/files", json=data, query_builder=query_builder)

    async def delete_files(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple files based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering files.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/files", query_builder=query_builder)

    # =============================================================================
    # FILE DIRECTORIES ENDPOINTS
    # =============================================================================
    async def get_file_directories_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for file directories, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for file directories
        """
        return await self.get_entity_meta("file_directories", query_builder)

    async def get_file_directories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get file directories from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: File directories data
        """
        return await self.get("/api/file_directories", query_builder=query_builder)

    async def get_file_directory(
        self, directory_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific file directory by ID

        Args:
            directory_id: Directory
            query_builder: Optional query builder for filtering
        Returns:
            Dict: File directory data
        """
        return await self.get(
            f"/api/file_directories/{directory_id}",
            query_builder=query_builder,
        )

    async def create_file_directory(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new file directory

        Args:
            data: Directory data

        Returns:
            Dict: Created directory data
        """
        return await self.post(
            "/api/file_directories",
            json=data,
        )

    async def patch_file_directory(
        self, directory_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a file directory

        Args:
            directory_id: Directory ID
            data: Partial directory data

        Returns:
            Dict: Updated directory data
        """
        return await self.patch(
            f"/api/file_directories/{directory_id}",
            json=data,
        )

    async def delete_file_directory(self, directory_id: int) -> Dict[str, Any]:
        """
        Delete a file directory

        Args:
            directory_id: Directory
        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/file_directories/{directory_id}")

    async def patch_file_directories(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple file directories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering directories.
            data: Data to update in the directories.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/file_directories", json=data, query_builder=query_builder
        )

    async def delete_file_directories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple file directories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering directories.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/file_directories", query_builder=query_builder)

    async def generate_file_directory_pdf(
        self, directory_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a file directory.

        Args:
            directory_id: The ID of the directory to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "file_directories", directory_id, template_id
        )

    # =============================================================================
    # FILE DIRECTORY CREDENTIALS ENDPOINTS
    # =============================================================================
    async def get_file_directory_credentials_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for file directory credentials, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for file directory credentials
        """
        return await self.get_entity_meta("file_directory_credentials", query_builder)

    async def get_file_directory_credentials(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get file directory credentials from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: File directory credentials data
        """
        return await self.get(
            "/api/file_directory_credentials", query_builder=query_builder
        )

    async def get_file_directory_credential(
        self, credential_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific file directory credential by ID

        Args:
            credential_id: Credential ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: File directory credential data
        """
        return await self.get(
            f"/api/file_directory_credentials/{credential_id}",
            query_builder=query_builder,
        )

    async def create_file_directory_credential(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new file directory credential

        Args:
            data: Credential data

        Returns:
            Dict: Created credential data
        """
        return await self.post(
            "/api/file_directory_credentials",
            json=data,
        )

    async def patch_file_directory_credential(
        self, credential_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a file directory credential

        Args:
            credential_id: Credential ID
            data: Partial credential data

        Returns:
            Dict: Updated credential data
        """
        return await self.patch(
            f"/api/file_directory_credentials/{credential_id}",
            json=data,
        )

    async def delete_file_directory_credential(
        self, credential_id: int
    ) -> Dict[str, Any]:
        """
        Delete a file directory credential

        Args:
            credential_id: Credential ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/file_directory_credentials/{credential_id}")

    async def patch_file_directory_credentials(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple file directory credentials based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering credentials.
            data: Data to update in the credentials.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/file_directory_credentials", json=data, query_builder=query_builder
        )

    async def delete_file_directory_credentials(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple file directory credentials based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering credentials.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/file_directory_credentials", query_builder=query_builder
        )

    async def generate_file_directory_credential_pdf(
        self, credential_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a file directory credential.

        Args:
            credential_id: The ID of the credential to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "file_directory_credentials", credential_id, template_id
        )

    # =============================================================================
    # PLACES ENDPOINTS
    # =============================================================================
    async def get_places_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for places, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for places
        """
        return await self.get_entity_meta("places", query_builder)

    async def get_places(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get places from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Places data
        """
        return await self.get("/api/places", query_builder=query_builder)

    async def get_place(
        self, place_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific place by ID

        Args:
            place_id: Place ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Place data
        """
        return await self.get(
            f"/api/places/{place_id}",
            query_builder=query_builder,
        )

    async def create_place(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new place

        Args:
            data: Place data

        Returns:
            Dict: Created place data
        """
        return await self.post(
            "/api/places",
            json=data,
        )

    async def patch_place(self, place_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially update a place

        Args:
            place_id: Place ID
            data: Partial place data

        Returns:
            Dict: Updated place data
        """
        return await self.patch(
            f"/api/places/{place_id}",
            json=data,
        )

    async def delete_place(self, place_id: int) -> Dict[str, Any]:
        """
        Delete a place

        Args:
            place_id: Place ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/places/{place_id}")

    async def patch_places(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple places based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering places.
            data: Data to update in the places.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch("/api/places", json=data, query_builder=query_builder)

    async def delete_places(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple places based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering places.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/places", query_builder=query_builder)

    async def generate_place_pdf(self, place_id: int, template_id: int = "0"):
        """
        Generate a PDF for a place.

        Args:
            place_id: The ID of the place to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf("places", place_id, template_id)

    # =============================================================================
    # PLACE ATTRIBUTES ENDPOINTS
    # =============================================================================
    async def get_place_attributes_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for place attributes, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for place attributes
        """
        return await self.get_entity_meta("place_attributes", query_builder)

    async def get_place_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get place attributes from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Place attributes data
        """
        return await self.get("/api/place_attributes", query_builder=query_builder)

    async def get_place_attribute(
        self, attribute_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific place attribute by ID

        Args:
            attribute_id: Attribute ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Place attribute data
        """
        return await self.get(
            f"/api/place_attributes/{attribute_id}",
            query_builder=query_builder,
        )

    async def create_place_attribute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new place attribute

        Args:
            data: Attribute data

        Returns:
            Dict: Created attribute data
        """
        return await self.post(
            "/api/place_attributes",
            json=data,
        )

    async def patch_place_attribute(
        self, attribute_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a place attribute

        Args:
            attribute_id: Attribute ID
            data: Partial attribute data

        Returns:
            Dict: Updated attribute data
        """
        return await self.patch(
            f"/api/place_attributes/{attribute_id}",
            json=data,
        )

    async def delete_place_attribute(self, attribute_id: int) -> Dict[str, Any]:
        """
        Delete a place attribute

        Args:
            attribute_id: Attribute ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/place_attributes/{attribute_id}")

    async def patch_place_attributes(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple place attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.
            data: Data to update in the attributes.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/place_attributes", json=data, query_builder=query_builder
        )

    async def delete_place_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple place attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/place_attributes", query_builder=query_builder)

    async def generate_place_attribute_pdf(
        self, attribute_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a place attribute.

        Args:
            attribute_id: The ID of the attribute to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "place_attributes", attribute_id, template_id
        )

    # =============================================================================
    # ESTIMATED QUANTITIES ENDPOINTS
    # =============================================================================
    async def get_estimated_quantities_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for estimated quantities, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for estimated quantities
        """
        return await self.get_entity_meta("estimated_quantities", query_builder)

    async def get_estimated_quantities(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get estimated quantities from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Estimated quantities data
        """
        return await self.get("/api/estimated_quantities", query_builder=query_builder)

    async def get_estimated_quantity(
        self, quantity_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific estimated quantity by ID

        Args:
            quantity_id: Quantity ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Estimated quantity data
        """
        return await self.get(
            f"/api/estimated_quantities/{quantity_id}",
            query_builder=query_builder,
        )

    async def create_estimated_quantity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new estimated quantity

        Args:
            data: Quantity data

        Returns:
            Dict: Created quantity data
        """
        return await self.post(
            "/api/estimated_quantities",
            json=data,
        )

    async def patch_estimated_quantity(
        self, quantity_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update an estimated quantity

        Args:
            quantity_id: Quantity ID
            data: Partial quantity data

        Returns:
            Dict: Updated quantity data
        """
        return await self.patch(
            f"/api/estimated_quantities/{quantity_id}",
            json=data,
        )

    async def delete_estimated_quantity(self, quantity_id: int) -> Dict[str, Any]:
        """
        Delete an estimated quantity

        Args:
            quantity_id: Quantity ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/estimated_quantities/{quantity_id}")

    async def patch_estimated_quantities(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple estimated quantities based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering quantities.
            data: Data to update in the quantities.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/estimated_quantities", json=data, query_builder=query_builder
        )

    async def delete_estimated_quantities(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple estimated quantities based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering quantities.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/estimated_quantities", query_builder=query_builder
        )

    async def generate_estimated_quantity_pdf(
        self, quantity_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for an estimated quantity.

        Args:
            quantity_id: The ID of the quantity to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "estimated_quantities", quantity_id, template_id
        )

    #  =============================================================================
    # EXTERNAL MARKER ENDPOINTS !!TODO!!
    # ==============================================================================

    # =============================================================================
    # PRICE PRODUCT GROUPS
    # =============================================================================
    async def get_price_product_groups_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for price product groups, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for price product groups
        """
        return await self.get_entity_meta("price_product_groups", query_builder)

    async def get_price_product_groups(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get price product groups from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Price product groups data
        """
        return await self.get("/api/price_product_groups", query_builder=query_builder)

    async def get_price_product_group(
        self, group_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific price product group by ID

        Args:
            group_id: Group ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Price product group data
        """
        return await self.get(
            f"/api/price_product_groups/{group_id}",
            query_builder=query_builder,
        )

    async def create_price_product_group(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new price product group

        Args:
            data: Group data

        Returns:
            Dict: Created group data
        """
        return await self.post(
            "/api/price_product_groups",
            json=data,
        )

    async def patch_price_product_group(
        self, group_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a price product group

        Args:
            group_id: Group ID
            data: Partial group data

        Returns:
            Dict: Updated group data
        """
        return await self.patch(
            f"/api/price_product_groups/{group_id}",
            json=data,
        )

    async def delete_price_product_group(self, group_id: int) -> Dict[str, Any]:
        """
        Delete a price product group

        Args:
            group_id: Group ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/price_product_groups/{group_id}")

    async def patch_price_product_groups(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple price product groups based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering groups.
            data: Data to update in the groups.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/price_product_groups", json=data, query_builder=query_builder
        )

    async def delete_price_product_groups(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple price product groups based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering groups.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/price_product_groups", query_builder=query_builder
        )

    async def generate_price_product_group_pdf(
        self, group_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a price product group.

        Args:
            group_id: The ID of the group to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "price_product_groups", group_id, template_id
        )

    # =============================================================================
    # PRODUCTS ENDPOINTS
    # =============================================================================

    async def get_products_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for products, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for products
        """
        return await self.get_entity_meta("products", query_builder)

    async def get_products(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get products from SW API
        Args:
            query_builder: Optional query builder for filtering and pagination
        Returns:
            Dict: Products data
        """
        return await self.get("/api/products", query_builder=query_builder)

    async def get_product(
        self, product_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific product by ID.
        Args:
            product_id: Product ID
            query_builder: Optional query builder for filtering
        Returns:
            Dict: Product data
        """

        return await self.get(
            f"/api/products/{product_id}", query_builder=query_builder
        )

    async def create_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new product.
        Args:
            data: Product data to create

        Returns:
            Dict: Created product data
        """
        return await self.post("/api/products", json=data)

    async def patch_product(
        self, product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a product.
        Args:
            product_id: Product ID to update
            data: Partial product data to update
        Returns:
            Dict: Updated product data
        """
        return await self.patch(
            f"/api/products/{product_id}",
            json=data,
        )

    async def delete_product(self, product_id: int) -> Dict[str, Any]:
        """
        Delete a product by ID.
        Args:
            product_id: Product ID to delete
        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/products/{product_id}")

    async def patch_products(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple products based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering products.
            data: Data to update in the products.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch("/api/products", json=data, query_builder=query_builder)

    async def delete_products(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple products based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering products.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/products", query_builder=query_builder)

    async def generate_product_pdf(self, product_id: int, template_id: int = "0"):
        """
        Generate a PDF for a product.

        Args:
            product_id: The ID of the product to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf("products", product_id, template_id)

    # =============================================================================
    # PRODUCT ATTRIBUTES ENDPOINTS
    # =============================================================================
    async def get_product_attributes_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for product attributes, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for product attributes
        """
        return await self.get_entity_meta("product_attributes", query_builder)

    async def get_product_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get product attributes from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Product attributes data
        """
        return await self.get("/api/product_attributes", query_builder=query_builder)

    async def get_product_attribute(
        self, attribute_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific product attribute by ID

        Args:
            attribute_id: Attribute ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Product attribute data
        """
        return await self.get(
            f"/api/product_attributes/{attribute_id}",
            query_builder=query_builder,
        )

    async def create_product_attribute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new product attribute

        Args:
            data: Attribute data

        Returns:
            Dict: Created attribute data
        """
        return await self.post(
            "/api/product_attributes",
            json=data,
        )

    async def patch_product_attribute(
        self, attribute_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a product attribute

        Args:
            attribute_id: Attribute ID
            data: Partial attribute data

        Returns:
            Dict: Updated attribute data
        """
        return await self.patch(
            f"/api/product_attributes/{attribute_id}",
            json=data,
        )

    async def delete_product_attribute(self, attribute_id: int) -> Dict[str, Any]:
        """
        Delete a product attribute

        Args:
            attribute_id: Attribute ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/product_attributes/{attribute_id}")

    async def patch_product_attributes(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple product attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.
            data: Data to update in the attributes.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/product_attributes", json=data, query_builder=query_builder
        )

    async def delete_product_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple product attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/product_attributes", query_builder=query_builder)

    async def generate_product_attribute_pdf(
        self, attribute_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a product attribute.

        Args:
            attribute_id: The ID of the attribute to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "product_attributes", attribute_id, template_id
        )

    # =============================================================================
    # PRODUCT CATEGORIES ENDPOINTS
    # =============================================================================

    async def get_product_categories_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for product categories, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for product categories
        """
        return await self.get_entity_meta("product_categories", query_builder)

    async def get_product_categories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get product categories from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Product categories data
        """
        return await self.get("/api/product_categories", query_builder=query_builder)

    async def get_product_category(
        self, category_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific product category by ID

        Args:
            category_id: Category ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Product category data
        """
        return await self.get(
            f"/api/product_categories/{category_id}",
            query_builder=query_builder,
        )

    async def create_product_category(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new product category

        Args:
            data: Category data

        Returns:
            Dict: Created category data
        """
        return await self.post(
            "/api/product_categories",
            json=data,
        )

    async def patch_product_category(
        self, category_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a product category

        Args:
            category_id: Category ID
            data: Partial category data

        Returns:
            Dict: Updated category data
        """
        return await self.patch(
            f"/api/product_categories/{category_id}",
            json=data,
        )

    async def delete_product_category(self, category_id: int) -> Dict[str, Any]:
        """
        Delete a product category

        Args:
            category_id: Category ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/product_categories/{category_id}")

    async def patch_product_categories(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple product categories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering categories.
            data: Data to update in the categories.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/product_categories", json=data, query_builder=query_builder
        )

    async def delete_product_categories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple product categories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering categories.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/product_categories", query_builder=query_builder)

    async def generate_product_category_pdf(
        self, category_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a product category.

        Args:
            category_id: The ID of the category to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "product_categories", category_id, template_id
        )

    # =============================================================================
    # PRODUCT TEMPLATES ENDPOINTS
    # =============================================================================
    async def get_product_templates_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for product templates, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for product templates
        """
        return await self.get_entity_meta("product_templates", query_builder)

    async def get_product_templates(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get product templates from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Product templates data
        """
        return await self.get("/api/product_templates", query_builder=query_builder)

    async def get_product_template(
        self, template_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific product template by ID

        Args:
            template_id: Template ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Product template data
        """
        return await self.get(
            f"/api/product_templates/{template_id}",
            query_builder=query_builder,
        )

    async def create_product_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new product template

        Args:
            data: Template data

        Returns:
            Dict: Created template data
        """
        return await self.post(
            "/api/product_templates",
            json=data,
        )

    async def patch_product_template(
        self, template_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a product template

        Args:
            template_id: Template ID
            data: Partial template data

        Returns:
            Dict: Updated template data
        """
        return await self.patch(
            f"/api/product_templates/{template_id}",
            json=data,
        )

    async def delete_product_template(self, template_id: int) -> Dict[str, Any]:
        """
        Delete a product template

        Args:
            template_id: Template ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/product_templates/{template_id}")

    async def patch_product_templates(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple product templates based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering templates.
            data: Data to update in the templates.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/product_templates", json=data, query_builder=query_builder
        )

    async def delete_product_templates(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple product templates based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering templates.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/product_templates", query_builder=query_builder)

    # !!TODO!!
    # async def generate_product_template_pdf()

    # =============================================================================
    # PRODUCT TO PRODUCT CATEGORIES ENDPOINTS
    # =============================================================================
    async def get_product_to_product_categories_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for product to product categories, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for product to product categories
        """
        return await self.get_entity_meta(
            "product_to_product_categories", query_builder
        )

    async def get_product_to_product_categories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get product to product categories from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Product to product categories data
        """
        return await self.get(
            "/api/product_to_product_categories", query_builder=query_builder
        )

    async def get_product_to_product_category(
        self, category_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific product to product category by ID

        Args:
            category_id: Category ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Product to product category data
        """
        return await self.get(
            f"/api/product_to_product_categories/{category_id}",
            query_builder=query_builder,
        )

    async def create_product_to_product_category(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new product to product category

        Args:
            data: Category data

        Returns:
            Dict: Created category data
        """
        return await self.post(
            "/api/product_to_product_categories",
            json=data,
        )

    async def patch_product_to_product_category(
        self, category_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a product to product category

        Args:
            category_id: Category ID
            data: Partial category data

        Returns:
            Dict: Updated category data
        """
        return await self.patch(
            f"/api/product_to_product_categories/{category_id}",
            json=data,
        )

    async def delete_product_to_product_category(
        self, category_id: int
    ) -> Dict[str, Any]:
        """
        Delete a product to product category

        Args:
            category_id: Category ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/product_to_product_categories/{category_id}")

    async def patch_product_to_product_categories(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple product to product categories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering categories.
            data: Data to update in the categories.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/product_to_product_categories", json=data, query_builder=query_builder
        )

    async def delete_product_to_product_categories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple product to product categories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering categories.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/product_to_product_categories", query_builder=query_builder
        )

    async def generate_product_to_product_category_pdf(
        self, category_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a product to product category.

        Args:
            category_id: The ID of the category to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "product_to_product_categories", category_id, template_id
        )

    # =============================================================================
    # SERVICED PRODUCTS ENDPOINTS
    # =============================================================================

    async def get_serviced_products_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for serviced products, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for serviced products
        """
        return await self.get_entity_meta("serviced_products", query_builder)

    async def get_serviced_products(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get serviced products from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Serviced products data
        """
        return await self.get("/api/serviced_products", query_builder=query_builder)

    async def get_serviced_product(
        self, serviced_product_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific serviced product by ID

        Args:
            serviced_product_id: Serviced product ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Serviced product data
        """
        return await self.get(
            f"/api/serviced_products/{serviced_product_id}",
            query_builder=query_builder,
        )

    async def create_serviced_product(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new serviced product.

        Args:
            data: Serviced product data to create

        Returns:
            Dict: Created serviced product data
        """
        return await self.post("/api/serviced_products", json=data)

    async def patch_serviced_product(
        self, serviced_product_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a serviced product.

        Args:
            serviced_product_id: Serviced product ID to update
            data: Partial serviced product data to update

        Returns:
            Dict: Updated serviced product data
        """
        return await self.patch(
            f"/api/serviced_products/{serviced_product_id}",
            json=data,
        )

    async def delete_serviced_product(self, serviced_product_id: int) -> Dict[str, Any]:
        """
        Delete a serviced product by ID.

        Args:
            serviced_product_id: Serviced product ID to delete

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/serviced_products/{serviced_product_id}")

    async def patch_serviced_products(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple serviced products based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering serviced products.
            data: Data to update in the serviced products.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/serviced_products", json=data, query_builder=query_builder
        )

    async def delete_serviced_products(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple serviced products based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering serviced products.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/serviced_products", query_builder=query_builder)

    async def generate_serviced_product_pdf(
        self, serviced_product_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a serviced product.

        Args:
            serviced_product_id: The ID of the serviced product to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "serviced_products", serviced_product_id, template_id
        )

    # =============================================================================
    # SERVICED PRODUCT ATTRIBUTES ENDPOINTS
    # =============================================================================

    async def get_serviced_product_attributes_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for serviced product attributes, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for serviced product attributes
        """
        return await self.get_entity_meta("serviced_product_attributes", query_builder)

    async def get_serviced_product_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get serviced product attributes from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Serviced product attributes data
        """
        return await self.get(
            "/api/serviced_product_attributes", query_builder=query_builder
        )

    async def get_serviced_product_attribute(
        self, attribute_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific serviced product attribute by ID

        Args:
            attribute_id: Attribute ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Serviced product attribute data
        """
        return await self.get(
            f"/api/serviced_product_attributes/{attribute_id}",
            query_builder=query_builder,
        )

    async def create_serviced_product_attribute(
        self, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new serviced product attribute

        Args:
            data: Attribute data

        Returns:
            Dict: Created attribute data
        """
        return await self.post(
            "/api/serviced_product_attributes",
            json=data,
        )

    async def patch_serviced_product_attribute(
        self, attribute_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a serviced product attribute

        Args:
            attribute_id: Attribute ID
            data: Partial attribute data

        Returns:
            Dict: Updated attribute data
        """
        return await self.patch(
            f"/api/serviced_product_attributes/{attribute_id}",
            json=data,
        )

    async def delete_serviced_product_attribute(
        self, attribute_id: int
    ) -> Dict[str, Any]:
        """
        Delete a serviced product attribute

        Args:
            attribute_id: Attribute ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/serviced_product_attributes/{attribute_id}")

    async def patch_serviced_product_attributes(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple serviced product attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.
            data: Data to update in the attributes.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/serviced_product_attributes", json=data, query_builder=query_builder
        )

    async def delete_serviced_product_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple serviced product attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete(
            "/api/serviced_product_attributes", query_builder=query_builder
        )

    async def generate_serviced_product_attribute_pdf(
        self, attribute_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a serviced product attribute.

        Args:
            attribute_id: The ID of the attribute to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "serviced_product_attributes", attribute_id, template_id
        )

    # =============================================================================
    # COMMISSIONS USER USERS ENDPOINTS
    # =============================================================================

    async def get_commissions_users_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for commissions users, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for commissions users
        """
        return await self.get_entity_meta("commissions_users_userss", query_builder)
    
    async def get_commissions_users(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get commissions users from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Commissions users data
        """
        return await self.get("/api/commissions_users_userss", query_builder=query_builder)
    
    async def get_commissions_user(
        self, user_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific commissions user by ID

        Args:
            user_id: User ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: Commissions user data
        """
        return await self.get(
            f"/api/commissions_users_userss/{user_id}",
            query_builder=query_builder,
        )
    async def create_commissions_user(self, data: Dict[str, Any]) -> Dict[str, Any]:

        """
        Create a new commissions user.

        Args:
            data: Commissions user data to create

        Returns:
            Dict: Created commissions user data
        """
        return await self.post("/api/commissions_users_userss", json=data)
    
    async def patch_commissions_user(
        self, user_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a commissions user.

        Args:
            user_id: Commissions user ID to update
            data: Partial commissions user data to update

        Returns:
            Dict: Updated commissions user data
        """
        return await self.patch(
            f"/api/commissions_users_userss/{user_id}",
            json=data,
        )

    async def delete_commissions_user(self, user_id: int) -> Dict[str, Any]:
        """
        Delete a commissions user by ID.

        Args:
            user_id: Commissions user ID to delete

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/commissions_users_userss/{user_id}")
    
    async def patch_commissions_users(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple commissions users based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering commissions users.
            data: Data to update in the commissions users.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/commissions_users_userss", json=data, query_builder=query_builder
        )

    async def delete_commissions_users(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple commissions users based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering commissions users.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/commissions_users_userss", query_builder=query_builder)

    async def generate_commissions_user_pdf(
        self, user_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a commissions user.

        Args:
            user_id: The ID of the commissions user to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "commissions_users_userss", user_id, template_id
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
    # USER USERS ENDPOINTS
    # =============================================================================
    async def get_users_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for users, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for users
        """
        return await self.get_entity_meta("user_users", query_builder)
    
    async def get_users(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get users from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Users data
        """
        return await self.get("/api/user_users", query_builder=query_builder)
    
    async def get_user(
        self, user_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific user by ID

        Args:
            user_id: User ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: User data
        """
        return await self.get(
            f"/api/user_users/{user_id}",
            query_builder=query_builder,
        )
    
    async def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user.

        Args:
            data: User data to create

        Returns:
            Dict: Created user data
        """
        return await self.post("/api/user_users", json=data)

    async def patch_user(
        self, user_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a user.

        Args:
            user_id: User ID to update
            data: Partial user data to update

        Returns:
            Dict: Updated user data
        """
        return await self.patch(
            f"/api/user_users/{user_id}",
            json=data,
        )
    
    async def delete_user(self, user_id: int) -> Dict[str, Any]:
        """
        Delete a user by ID.

        Args:
            user_id: User ID to delete

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/user_users/{user_id}")

    async def patch_users(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple users based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering users.
            data: Data to update in the users.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/user_users", json=data, query_builder=query_builder
        )
    
    async def delete_users(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:

        """
        Delete multiple users based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering users.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/user_users", query_builder=query_builder)
    
    async def generate_user_pdf(self, user_id: int, template_id: int = "0"):
        """
        Generate a PDF for a user.

        Args:
            user_id: The ID of the user to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf("user_users", user_id, template_id)

    
    # =============================================================================
    # UserUserAbsence  ENDPOINTS !!TODO!!
    # =============================================================================

    # =============================================================================
    # UserUserAbsenceLimit  ENDPOINTS !!TODO!!
    # =============================================================================

    # =============================================================================
    # USER USER ATTRIBUTES ENDPOINTS
    # =============================================================================

    async def get_user_attributes_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for user attributes, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for user attributes
        """
        return await self.get_entity_meta("user_user_attributes", query_builder)
    
    async def get_user_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get user attributes from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: User attributes data
        """
        return await self.get("/api/user_user_attributes", query_builder=query_builder)

    async def get_user_attribute(
        self, attribute_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific user attribute by ID

        Args:
            attribute_id: Attribute ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: User attribute data
        """
        return await self.get(
            f"/api/user_user_attributes/{attribute_id}",
            query_builder=query_builder,
        )
    
    async def create_user_attribute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user attribute

        Args:
            data: Attribute data

        Returns:
            Dict: Created attribute data
        """
        return await self.post(
            "/api/user_user_attributes",
            json=data,
        )

    async def patch_user_attribute(
        self, attribute_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a user attribute

        Args:
            attribute_id: Attribute ID
            data: Partial attribute data

        Returns:
            Dict: Updated attribute data
        """
        return await self.patch(
            f"/api/user_user_attributes/{attribute_id}",
            json=data,
        )

    async def delete_user_attribute(self, attribute_id: int) -> Dict[str, Any]:
        """
        Delete a user attribute

        Args:
            attribute_id: Attribute ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/user_user_attributes/{attribute_id}")
    
    async def patch_user_attributes(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple user attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.
            data: Data to update in the attributes.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/user_user_attributes", json=data, query_builder=query_builder
        )

    async def delete_user_attributes(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple user attributes based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering attributes.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/user_user_attributes", query_builder=query_builder)
    
    async def generate_user_attribute_pdf(
        self, attribute_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a user attribute.

        Args:
            attribute_id: The ID of the attribute to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "user_user_attributes", attribute_id, template_id
        )
    
    # =============================================================================
    # USER USER HISTORIES ENDPOINTS
    # =============================================================================
    async def get_user_histories_meta(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for user histories, including field information.

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: Metadata for user histories
        """
        return await self.get_entity_meta("user_user_histories", query_builder)
    
    async def get_user_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get user histories from SW API

        Args:
            query_builder: Optional query builder for filtering and pagination

        Returns:
            Dict: User histories data
        """
        return await self.get("/api/user_user_histories", query_builder=query_builder)

    async def get_user_history(
        self, history_id: int, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Get a specific user history by ID

        Args:
            history_id: History ID
            query_builder: Optional query builder for filtering

        Returns:
            Dict: User history data
        """
        return await self.get(
            f"/api/user_user_histories/{history_id}",
            query_builder=query_builder,
        )

    async def create_user_history(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user history

        Args:
            data: History data

        Returns:
            Dict: Created history data
        """
        return await self.post(
            "/api/user_user_histories",
            json=data,
        )

    async def patch_user_history(
        self, history_id: int, data
: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Partially update a user history

        Args:
            history_id: History ID
            data: Partial history data

        Returns:
            Dict: Updated history data
        """
        return await self.patch(
            f"/api/user_user_histories/{history_id}",
            json=data,
        )

    async def delete_user_history(self, history_id: int) -> Dict[str, Any]:
        """
        Delete a user history

        Args:
            history_id: History ID

        Returns:
            Dict: Deletion result
        """
        return await self.delete(f"/api/user_user_histories/{history_id}")
    
    async def patch_user_histories(
        self,
        query_builder: Optional["SWQueryBuilder"] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Partially update multiple user histories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering histories.
            data: Data to update in the histories.

        Returns:
            Dict: Result of the patch operation.
        """
        if not data:
            raise SWException("Data for patching must be provided.")

        return await self.patch(
            "/api/user_user_histories", json=data, query_builder=query_builder
        )
    
    async def delete_user_histories(
        self, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Delete multiple user histories based on query parameters.

        Args:
            query_builder: Optional SWQueryBuilder for filtering histories.

        Returns:
            Dict: Result of the delete operation.
        """
        return await self.delete("/api/user_user_histories", query_builder=query_builder)
    
    async def generate_user_history_pdf(
        self, history_id: int, template_id: int = "0"
    ):
        """
        Generate a PDF for a user history.

        Args:
            history_id: The ID of
                the user history to generate the PDF for.
            template_id: The ID of the template to use for the PDF. Defaults to "0" for default template.
        Returns:
            The binary content of the generated PDF.
        """
        return await self.get_entity_generate_pdf(
            "user_user_histories", history_id, template_id
        )

    # =============================================================================
    # UTILITY AND CORE ENDPOINTS
    # =============================================================================

    async def get_home(self) -> Dict[str, Any]:
        """
        Get homepage, check if API works
        Returns:
            Dict: Home data
        """
        return await self.get("/api/home")

    async def get_me(self) -> Dict[str, Any]:
        """
        Get the current user's information.
        Returns:
            Dict: User data
        """
        return await self.get("/api/me")

    async def upload_file(self, files: Dict[str, Any], mode: int = 0) -> Dict[str, Any]:
        """
        Upload file/ files. You should send the file (or files) in the data_files parameter, e.g. as form-data

        Request Body schema: multipart/form-data
        data_files
        required
        Array of strings <binary> (data_files)
        Files array

        mode
        integer (mode)
        (default: 0) 0: temporary file, 1: attachment, 2: file
        """
        
        return await self.post("/api/files/upload", json={"data_files": files, "mode": 0})

    async def upload_files_from_urls(self, urls: List[str]) -> Dict[str, Any]:
        """_summary_

        Args:
            urls (List[str]): _description_

        Returns:
            Dict[str, Any]: _description_
        """
        return await self.post("/api/files/upload/urls", json={"data_files_urls": urls})
    

    async def get_settings(self, module: str, query_builder: Optional["SWQueryBuilder"] = None) -> Dict[str, Any]:
        """
        Get settings for a specific module.

        Args:
            module: The name of the module (e.g., 'products').
            query_builder: Optional SWQueryBuilder for filtering and pagination.

        Returns:
            A dictionary containing the settings data.
        """
        return await self.get(f"/api/{module}/settings", query_builder=query_builder)
    
    async def get_setting(self, module: str, setting_id: int, query_builder: Optional["SWQueryBuilder"] = None) -> Dict[str, Any]:
        """
        Get a specific setting for a module by ID.

        Args:
            module: The name of the module (e.g., 'products').
            setting_id: The ID of the setting.
            query_builder: Optional SWQueryBuilder for filtering.

        Returns:
            A dictionary containing the setting data.
        """
        return await self.get(f"/api/{module}/settings/{setting_id}", query_builder=query_builder)
    

    async def get_setting_by_name(self, module: str, setting_name: str, query_builder: Optional["SWQueryBuilder"] = None) -> Dict[str, Any]:
        """
        Get a specific setting for a module by name.

        Args:
            module: The name of the module (e.g., 'products').
            setting_name: The name of the setting.
            query_builder: Optional SWQueryBuilder for filtering.

        Returns:
            A dictionary containing the setting data.
        """
        return await self.get(f"/api/{module}/settings/name/{setting_name}", query_builder=query_builder)
    
    async def patch_setting_by_name(
        self, module: str, setting_name: str, data: Dict[str, Any], query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:
        """
        Partially update a specific setting for a module by name.

        Args:
            module: The name of the module (e.g., 'products').
            setting_name: The name of the setting.
            data: Data to update in the setting.
            query_builder: Optional SWQueryBuilder for filtering.

        Returns:
            A dictionary containing the updated setting data.
        """
        return await self.patch(
            f"/api/{module}/settings/name/{setting_name}",
            json=data,
            query_builder=query_builder,
        )
    
    async def delete_setting_by_name(
        self, module: str, setting_name: str, query_builder: Optional["SWQueryBuilder"] = None
    ) -> Dict[str, Any]:    
        """
        Delete a specific setting for a module by name.

        Args:
            module: The name of the module (e.g., 'products').
            setting_name: The name of the setting.
            query_builder: Optional SWQueryBuilder for filtering.

        Returns:
            A dictionary containing the deletion result.
        """
        return await self.delete(
            f"/api/{module}/settings/name/{setting_name}",
            query_builder=query_builder,
        )
    


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

