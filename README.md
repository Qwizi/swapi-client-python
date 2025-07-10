# SW-API-Client

An asynchronous Python client for the Serwis Planner API.

## Features

-   Asynchronous design using `httpx` and `asyncio`.
-   Token-based authentication.
-   Helper methods for all major API endpoints.
-   Generic helpers for `meta`, `autoselect`, `history`, and `audit` endpoints.
-   Pagination helper (`get_all_pages`) to easily fetch all results from paginated endpoints.
-   Powerful `SWQueryBuilder` for creating complex queries with filtering, sorting, and field selection.
-   No Pydantic models required; uses plain Python dictionaries for all data.

## Installation

First, install the package from PyPI:

```bash
pip install swapi-client
```

The client uses `python-dotenv` to manage environment variables for the example. Install it if you want to run the example code directly.

```bash
pip install python-dotenv
```

## Usage

### Configuration

Create a `.env` file in your project root to store your API credentials:

```env
SW_API_URL=https://your-api-url.com
SW_CLIENT_ID=your_client_id
SW_AUTH_TOKEN=your_auth_token
SW_LOGIN=your_login_email
SW_PASSWORD=your_password
```

### Example

Here is a complete example demonstrating how to log in, fetch data, and use the query builder.

```python
import asyncio
import os
import pprint
from dotenv import load_dotenv
from swapi_client import SWApiClient, SWQueryBuilder

# Load environment variables from .env file
load_dotenv()

async def main():
    """
    Main function to demonstrate the usage of the SWApiClient.
    """
    api_url = os.getenv("SW_API_URL")
    client_id = os.getenv("SW_CLIENT_ID")
    auth_token = os.getenv("SW_AUTH_TOKEN")
    login_user = os.getenv("SW_LOGIN")
    password = os.getenv("SW_PASSWORD")

    if not all([api_url, client_id, auth_token, login_user, password]):
        print("Please set all required environment variables in a .env file.")
        return

    # The client is used within an async context manager
    async with SWApiClient(api_url) as client:
        try:
            # 1. Login to get an authentication token
            print("Attempting to log in...")
            token = await client.login(
                clientId=client_id,
                authToken=auth_token,
                login=login_user,
                password=password,
            )
            print(f"Successfully logged in. Token starts with: {token[:10]}...")

            # 2. Verify the token and get current user info
            me = await client.get_me()
            print(f"Token verified. Logged in as: {me.get('user', {}).get('username')}")
            print("-" * 30)

            # 3. Example: Get all account companies using the pagination helper
            print("Fetching all account companies (with pagination)...")
            all_companies = await client.get_all_pages(client.get_account_companies)
            print(f"Found a total of {len(all_companies)} companies.")
            if all_companies:
                print(f"First company: {all_companies[0].get('name')}")
            print("-" * 30)

            # 4. Example: Use the SWQueryBuilder to filter, sort, and select fields
            print("Fetching filtered companies...")
            query = (
                SWQueryBuilder()
                .filter("name", "STB", "contains")
                .order("name", "asc")
                .fields(["id", "name", "email"])
                .page_limit(5)
            )
            filtered_companies_response = await client.get_account_companies(query_builder=query)
            filtered_companies = filtered_companies_response.get('data', [])
            print(f"Found {len(filtered_companies)} companies matching the filter.")
            pprint.pprint(filtered_companies)
            print("-" * 30)

            # 5. Example: Get metadata for a module
            print("Fetching metadata for the 'products' module...")
            products_meta = await client.get_entity_meta("products")
            print("Available fields for products (first 5):")
            for field, details in list(products_meta.get('data', {}).get('fields', {}).items())[:5]:
                 print(f"  - {field}: {details.get('label')}")
            print("-" * 30)

            # 6. Example: Use for_metadata to get dynamic metadata
            print("Fetching metadata for a serviced product with specific attributes...")
            meta_query = SWQueryBuilder().for_metadata({"id": 1, "commissionPhase": 1})
            serviced_product_meta = await client.get_entity_meta(
                "serviced_products", query_builder=meta_query
            )
            print("Metadata for serviced product with for[id]=1 and for[commissionPhase]=1:")
            pprint.pprint(serviced_product_meta.get('data', {}).get('fields', {}).get('commission'))

        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

## SWQueryBuilder

The `SWQueryBuilder` provides a fluent interface to construct complex query parameters for the API.

| Method                                | Description                                                                                             |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `fields(["field1", "field2"])`        | Specifies which fields to include in the response.                                                      |
| `extra_fields(["field1"])`            | Includes additional, non-default fields.                                                                |
| `for_metadata({"id": 1})`             | Simulates an object change to retrieve dynamic metadata (uses `for[fieldName]`).                        |
| `order("field", "desc")`              | Sorts the results by a field in a given direction (`asc` or `desc`).                                    |
| `page_limit(50)`                      | Sets the number of results per page.                                                                    |
| `page_offset(100)`                    | Sets the starting offset for the results.                                                               |
| `page_number(3)`                      | Sets the page number to retrieve.                                                                       |
| `filter("field", "value", "op")`      | Adds a filter condition. Operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `contains`, `in`, `isNull`, etc. |
| `filter_or({...}, group_index=0)`     | Adds a group of conditions where at least one must be true.                                             |
| `filter_and({...}, group_index=0)`    | Adds a group of conditions where all must be true.                                                      |
| `with_relations(True)`                | Includes related objects in the response.                                                               |
| `with_editable_settings_for_action()` | Retrieves settings related to a specific action.                                                        |
| `lang("en")`                          | Sets the language for the response.                                                                     |
| `build()`                             | Returns the dictionary of query parameters.                                                             |

## API Methods

The client provides a comprehensive set of methods for interacting with the Serwis Planner API. It includes specific methods for most endpoints (e.g., `get_products`, `create_account_user`) as well as generic helpers.

### Generic Helpers

-   `get_all_pages(paginated_method, ...)`: Automatically handles pagination for any list endpoint.
-   `get_entity_meta(module, ...)`: Fetches metadata for any module.
-   `get_entity_autoselect(module, ...)`: Fetches autoselect data for any module.
-   `get_entity_history(module, ...)`: Fetches history records for any module.
-   `get_entity_audit(module, ...)`: Fetches audit records for any module.

### Major Endpoints Covered

-   Account Companies
-   Account Users
-   Products & Serviced Products
-   Baskets & Basket Positions
-   Commissions
-   File Uploads
-   ODBC Reports
-   Email Messages
-   PDF Generation
-   History and Auditing
-   Bulk and Contextual Operations
-   Global Search
-   And many more...

Each endpoint has corresponding `get`, `create`, `update`, `patch`, and `delete` methods where applicable. For a full list of available methods, please refer to the source code in `src/swapi_client/client.py`.
