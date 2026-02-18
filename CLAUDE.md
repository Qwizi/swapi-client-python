# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`swapi-client` is a Python client library for the Serwis Planner API. It supports both **synchronous** and **asynchronous** usage. Resources are accessed as attributes of the client (Stripe-style), and query parameters are passed as kwargs — no separate query builder class.

## Development Commands

**Package Management:**
- This project uses `uv` for package management
- Install dependencies: `uv sync`
- Run tests: `uv run python test_filters.py`

**Building and Publishing:**
- Build package: `uv build`
- Publish to PyPI: `uv publish --token $PYPI_TOKEN` (handled by CI/CD)

**Python Version:**
- Required: Python 3.12+ (specified in `.python-version`)

## Architecture

### Core Components

**`_http.py`** — low-level HTTP clients
- `BaseSyncClient` — wraps `httpx.Client`; sync context manager (`with`)
- `BaseAsyncClient` — wraps `httpx.AsyncClient`; async context manager (`async with`)
- Both expose `set_token()`, `request()`, `get/post/put/patch/delete()`
- Error handling raises typed exceptions (see Exceptions section)

**`_params.py`** — query parameter builder
- Single function `build_params(**kwargs)` converts kwargs → flat URL params dict
- Called internally by every resource method; never used directly by end users

**`client.py`** — public entry points (~100 lines)
- `SWApiClient(BaseSyncClient)` — sync client; resources attached in `__init__`
- `AsyncSWApiClient(BaseAsyncClient)` — async client; resources attached in `__init__`
- Both expose `me()` / `await me()` → `/api/me` (current user data)

**`resources/`** — one file per domain, each with `Sync*` and `Async*` classes
- `_base.py` — `SyncResource` / `AsyncResource` with standard CRUD + `all()` auto-pagination
- `auth.py` — `login()`
- `account.py` — `AccountResource` → `.companies` + `.users`
- `commissions.py` — `CommissionsResource` → `.attributes` `.phases` `.scope_types` etc.
- `files.py` — `FilesResource` → `.directories` + `upload()` + `upload_from_urls()`
- `kanbans.py`, `places.py`
- `products.py` — `ProductsResource` → `.attributes` `.categories` `.templates` + `generate_pdf()`
- `serviced_products.py` — `ServicedProductsResource` → `.attributes` + `generate_pdf()`
- `users.py` — `UsersResource` + `UserProfilesResource`

**`exceptions.py`** — typed exception hierarchy (see below)

### Code Organization

```
src/swapi_client/
├── __init__.py              # Public exports
├── client.py                # SWApiClient + AsyncSWApiClient
├── exceptions.py            # Exception hierarchy
├── _http.py                 # BaseSyncClient + BaseAsyncClient
├── _params.py               # build_params()
└── resources/
    ├── __init__.py
    ├── _base.py             # SyncResource + AsyncResource
    ├── auth.py
    ├── account.py
    ├── commissions.py
    ├── files.py
    ├── kanbans.py
    ├── places.py
    ├── products.py
    ├── serviced_products.py
    └── users.py
```

## Usage

### Sync

```python
from swapi_client import SWApiClient

with SWApiClient("https://api.url") as client:
    client.auth.login(client_id="...", auth_token="...", login="...", password="...")

    user        = client.me()
    companies   = client.account.companies.list(filter={"name__contains": "STB"}, limit=50)
    company     = client.account.companies.retrieve(123)
    new_co      = client.account.companies.create({"name": "New Co"})
    updated     = client.account.companies.update(123, {"name": "Updated"})
    client.account.companies.delete(123)
    all_cos     = client.account.companies.all(filter={"status": "active"})

    phases      = client.commissions.phases.list()
    products    = client.products.list(filter={"attributes.476__hasText": "keyword"})
    pdf         = client.products.generate_pdf(product_id=123, template_id=1)
    uploaded    = client.files.upload(files={"file": open("doc.pdf", "rb")})
```

### Async

```python
from swapi_client import AsyncSWApiClient

async with AsyncSWApiClient("https://api.url") as client:
    await client.auth.login(client_id="...", auth_token="...", login="...", password="...")

    user      = await client.me()
    companies = await client.account.companies.list(filter={"name__contains": "STB"})
    all_cos   = await client.account.companies.all()
    phases    = await client.commissions.phases.list()
    pdf       = await client.products.generate_pdf(product_id=123, template_id=1)
```

## Query Parameters (kwargs)

All resource methods accept the following kwargs:

| kwarg | URL param | Example |
|-------|-----------|---------|
| `filter={"name__contains": "STB"}` | `filter[name][contains]=STB` | operator after `__` |
| `filter={"status": "active"}` | `filter[status][eq]=active` | no `__` → `eq` |
| `filter={"attributes.476__hasText": "x"}` | `filter[attributes][476][hasText]=x` | numeric segment → wiele nawiasów |
| `filter={"commissionPhase.commissionPhaseId": 1}` | `filter[commissionPhase.commissionPhaseId][eq]=1` | bez segmentu numerycznego → dot literalny |
| `filter_or=[{...}, {...}]` | `filterOr[0][...]=...` | list of dicts |
| `filter_and=[{...}, {...}]` | `filterAnd[0][...]=...` | list of dicts |
| `order={"name": "asc"}` | `order[name]=asc` | |
| `fields=["id", "name"]` | `fields=id,name` | |
| `extra_fields=["address"]` | `extra_fields=address` | |
| `limit=50` | `page[limit]=50` | |
| `page=1` | `page[number]=1` | |
| `offset=0` | `page[offset]=0` | |
| `with_relations=True` | `setting[with_relations]=true` | |
| `lang="pl"` | `setting[lang]=pl` | |
| `for_metadata={"id": 1}` | `for[id]=1` | |

Operators for `isNull` / `isNotNull`: use empty string as value, e.g. `filter={"deleted_at__isNull": ""}`.

## Exceptions

```
SWException (base)
├── SWHTTPError          — any HTTP error (has .status_code, .response_data)
│   ├── SWAuthenticationError  — 401
│   ├── SWForbiddenError       — 403
│   ├── SWNotFoundError        — 404
│   ├── SWValidationError      — 422 (has .errors with field-level details)
│   ├── SWRateLimitError       — 429
│   └── SWServerError          — 5xx
└── SWConnectionError    — network / timeout
```

All exceptions are importable directly from `swapi_client`:

```python
from swapi_client import SWNotFoundError, SWValidationError, SWConnectionError

try:
    client.account.companies.retrieve(999)
except SWNotFoundError:
    ...
except SWValidationError as e:
    print(e.errors)
except SWConnectionError:
    ...
```

## Adding New Resources

1. Create `src/swapi_client/resources/<name>.py` with `Sync<Name>Resource` and `Async<Name>Resource`
2. Inherit from `SyncResource` / `AsyncResource` and set `_path`
3. Add sub-resources in `__init__` if needed
4. Register on both `SWApiClient` and `AsyncSWApiClient` in `client.py`
5. Export from `resources/__init__.py`

## Authentication Flow

1. Create client instance with API URL
2. Enter context manager (`with` / `async with`)
3. Call `client.auth.login(client_id, auth_token, login, password)` — stores Bearer token automatically
4. All subsequent requests include the token

**Login endpoint** — note: no `/api/` prefix:
```
POST /_/security/login
Content-Type: application/json
{"clientId": "...", "authToken": "...", "login": "...", "password": "..."}
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

## REST Endpoint Specification

- Standard: OpenAPI 3.0
- Base path: `/api/...`
- Data format: `application/json`
- Authorization required for most endpoints

### Query Parameter Conventions

#### Filtering
```
filter[field][eq]=value
filter[id][gt]=10
filter[name][hasText]=abc
filter[attributes][476][hasText]=text    ← nested
filterOr[0][name][contains]=STB
filterAnd[0][status][eq]=active
```

#### Sorting
```
order[field]=asc
order[field]=desc
```

#### Field projection
```
fields=id,name,status
extra_fields=address,ph.fullName
```

#### Pagination
```
page[limit]=50
page[number]=1
page[offset]=0
```

#### System parameters
```
setting[with_relations]=true
setting[with_cache]=true
setting[limit_to_my_settings]=true
setting[lang]=pl
```
