# SW-API-Client

An asynchronous Python client for the Serwis Planner API.

## Features

-   Asynchronous design using `httpx` and `asyncio`.
-   Handles authentication, rate limiting, and error handling.
-   Provides methods for all major API endpoints.
-   Includes a pagination helper to easily fetch all results from paginated endpoints.
-   Uses plain Python dictionaries, no Pydantic models required.

## Installation

```bash
pip install swapi-client
```

## Usage

Here's a simple example of how to use the client to fetch account companies:

```python
import asyncio
from swapi_client import SWApiClient, SWQueryBuilder

async def main():
    api_url = "YOUR_API_URL"
    # You can initialize the client with a token directly
    # token = "YOUR_AUTH_TOKEN"
    # async with SWApiClient(api_url, token=token) as client:

    # Or, login to get a token
    async with SWApiClient(api_url) as client:
        try:
            # Login to get a token
            token = await client.login(
                clientId="YOUR_CLIENT_ID",
                authToken="YOUR_AUTH_TOKEN",
                login="YOUR_LOGIN",
                password="YOUR_PASSWORD"
            )
            print(f"Successfully logged in. Token: {token[:10]}...")

            # Verify the token works
            me = await client.verify_token()
            print(f"Token verified. User: {me.get('name')}")

            # Get all companies
            all_companies = await client.get_all_pages(client.get_account_companies)
            print(f"Found {len(all_companies)} companies.")

            # Get a specific company
            if all_companies:
                company_id = all_companies[0]['id']
                company = await client.get_account_company(company_id)
                print(f"Company details: {company}")

            # Use the query builder
            query = SWQueryBuilder().filter("name", "Test Company").page_limit(5)
            filtered_companies = await client.get_account_companies(query_builder=query)
            print(f"Filtered companies: {filtered_companies}")

        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

## API Methods

The client provides methods for the following API endpoints:

-   Account Companies
-   Account Users
-   Products
-   Serviced Products
-   Baskets
-   Basket Positions
-   Custom Serviced Products
-   File Uploads
-   ODBC Reports
-   Email Messages
-   PDF Generation
-   History and Auditing
-   Bulk Operations
-   Contextual Operations
-   Global Search

Each endpoint has corresponding `get`, `create`, `update`, `patch`, and `delete` methods where applicable.
