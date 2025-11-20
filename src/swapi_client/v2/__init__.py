"""High-level exports for the ``swapi_client.v2`` package.

This module re-exports the primary public API of the v2 package so users
can do:

	from swapi_client.v2 import SWAPIClient, Q, SWAPIQuerySet

and also access the `models` subpackage as `swapi_client.v2.models`.
"""

from .client import SWAPIClient
from .q import Q
from .queryset import SWAPIQuerySet, SWAPIListResponse
from .queryset_core import CoreQuerySet
from .dynamic import DynamicObject, DynamicList
from . import models

from .exceptions import (
	SWAPIError,
	SWAPIAuthError,
	SWAPINotFoundError,
	SWAPISchemaError,
	SWAPIValidationError,
	SWAPIPermissionDenied,
	SWAPIConnectionError,
)

from .utils import parse_filter_key, is_iterable_but_not_string, list_to_csv

__all__ = [
	"SWAPIClient",
	"Q",
	"SWAPIQuerySet",
	"SWAPIListResponse",
	"CoreQuerySet",
	"DynamicObject",
	"DynamicList",
	"models",
	# exceptions
	"SWAPIError",
	"SWAPIAuthError",
	"SWAPINotFoundError",
	"SWAPISchemaError",
	"SWAPIValidationError",
	"SWAPIPermissionDenied",
	"SWAPIConnectionError",
	# utils
	"parse_filter_key",
	"is_iterable_but_not_string",
	"list_to_csv",
]

