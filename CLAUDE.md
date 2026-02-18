# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`swapi-client` is an asynchronous Python client library for the Serwis Planner API. It provides a fluent interface for making API requests with complex filtering, pagination, and field selection capabilities.

## Development Commands

**Package Management:**
- This project uses `uv` for package management
- Install dependencies: `uv sync`
- Run tests: `python test_filters.py` (or `uv run python test_filters.py`)

**Building and Publishing:**
- Build package: `uv build`
- Publish to PyPI: `uv publish --token $PYPI_TOKEN` (handled by CI/CD)

**Python Version:**
- Required: Python 3.12+ (specified in `.python-version`)

## Architecture

### Core Components

**BaseSWApiClient** (`client.py:14-160`)
- Low-level HTTP client handling requests, authentication, and error handling
- Uses `httpx.AsyncClient` for async HTTP operations
- Implements async context manager protocol (`__aenter__`, `__aexit__`)
- Token-based authentication via Bearer header
- All API interactions must use `async with` context manager

**SWApiClient** (`client.py:163+`)
- High-level API client with ~5800 lines of endpoint-specific methods
- Inherits from `BaseSWApiClient`
- Provides methods for all Serwis Planner API endpoints:
  - Account management (companies, users)
  - Products and serviced products
  - Baskets and orders
  - Commissions
  - File uploads, ODBC reports, email, PDF generation
  - Generic helpers: `get_entity_meta()`, `get_entity_autoselect()`, `get_entity_history()`, `get_entity_audit()`
- Pagination helper: `get_all_pages(paginated_method, ...)` automatically fetches all pages

**SWQueryBuilder** (`query_builder.py`)
- Fluent interface for building complex query parameters
- Supports nested field paths: `filter(["attributes", "476"], "value", "hasText")`
- Convenience method: `filter_nested("attributes.476.hasText", "value")`
- Complex filters: `filter_or()` and `filter_and()` with group support
- Pagination: `page_limit()`, `page_offset()`, `page_number()`
- Field selection: `fields()`, `extra_fields()`
- Sorting: `order(field, direction)`
- Metadata simulation: `for_metadata({"id": 1})` for dynamic metadata
- All methods return `self` for chaining; call `build()` to get params dict

**SWException** (`exceptions.py`)
- Base exception class for all API errors
- Raised by `BaseSWApiClient.request()` on HTTP errors

### Key Patterns

**Authentication Flow:**
1. Create client instance with API URL
2. Use `async with` to initialize httpx client
3. Call `await client.login(clientId, authToken, login, password)` to get token
4. Token is automatically stored and used in subsequent requests

**Query Building:**
```python
query = (SWQueryBuilder()
    .filter("name", "value", "contains")
    .order("created_at", "desc")
    .page_limit(50)
    .fields(["id", "name", "email"])
)
response = await client.get_account_companies(query_builder=query)
```

**Pagination:**
```python
# Manual pagination
response = await client.get_products(query_builder=SWQueryBuilder().page_number(2))

# Automatic pagination
all_products = await client.get_all_pages(client.get_products)
```

## Code Organization

```
src/swapi_client/
├── __init__.py         # Package exports
├── client.py           # BaseSWApiClient + SWApiClient (main API methods)
├── query_builder.py    # SWQueryBuilder (fluent query interface)
└── exceptions.py       # SWException
```

## CI/CD

**Automatic Releases** (`.github/workflows/release.yml`)
- Triggered on push to `master` (excluding README/gitignore changes)
- Auto-increments patch version in `pyproject.toml`
- Creates git tag and GitHub release
- Commits include `[skip ci]` to prevent recursive triggers

**PyPI Publishing** (`.github/workflows/publish.yml`)
- Triggered on GitHub release publication
- Builds package with `uv build`
- Publishes to PyPI with `uv publish`

## Adding New Endpoints

When adding new API endpoint methods to `SWApiClient`:
1. Follow existing naming convention: `get_`, `create_`, `update_`, `patch_`, `delete_` prefixes
2. Accept optional `query_builder: SWQueryBuilder` parameter for list endpoints
3. Use `self.request(method, path, query_builder=query_builder, **kwargs)`
4. Return the JSON response dict directly
5. Add docstring with args and return type
6. Export in `__init__.py` if creating new classes

## Testing

Current test coverage is limited to `test_filters.py` which demonstrates `SWQueryBuilder` filtering capabilities. When adding tests:
- Place test files in project root or create a `tests/` directory
- Use descriptive function names: `test_<feature_name>()`
- Demonstrate practical usage patterns
