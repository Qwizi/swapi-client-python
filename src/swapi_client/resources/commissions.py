"""Commission resources."""
from typing import TYPE_CHECKING

from ._base import SyncResource, AsyncResource

if TYPE_CHECKING:
    from .._http import BaseSyncClient, BaseAsyncClient


# ── Sync ──────────────────────────────────────────────────────────────────────

class SyncCommissionAttributesCriteriasResource(SyncResource):
    _path = "/api/commission_attribute_criterias"


class SyncCommissionAttributesRelationsResource(SyncResource):
    _path = "/api/commission_attribute_relations"


class SyncCommissionAttributesResource(SyncResource):
    _path = "/api/commission_attributes"

    def __init__(self, client: "BaseSyncClient") -> None:
        super().__init__(client)
        self.criterias = SyncCommissionAttributesCriteriasResource(client)
        self.relations = SyncCommissionAttributesRelationsResource(client)


class SyncCommissionPhasesResource(SyncResource):
    _path = "/api/commission_phases"


class SyncCommissionScopeTypesResource(SyncResource):
    _path = "/api/commission_scope_types"


class SyncCommissionShortcutsResource(SyncResource):
    _path = "/api/commission_shortcuts"


class SyncCommissionUsersResource(SyncResource):
    _path = "/api/commission_users"


class SyncCommissionsResource(SyncResource):
    _path = "/api/commissions"

    def __init__(self, client: "BaseSyncClient") -> None:
        super().__init__(client)
        self.attributes = SyncCommissionAttributesResource(client)
        self.phases = SyncCommissionPhasesResource(client)
        self.scope_types = SyncCommissionScopeTypesResource(client)
        self.shortcuts = SyncCommissionShortcutsResource(client)
        self.users = SyncCommissionUsersResource(client)


# ── Async ─────────────────────────────────────────────────────────────────────

class AsyncCommissionAttributesCriteriasResource(AsyncResource):
    _path = "/api/commission_attribute_criterias"


class AsyncCommissionAttributesRelationsResource(AsyncResource):
    _path = "/api/commission_attribute_relations"


class AsyncCommissionAttributesResource(AsyncResource):
    _path = "/api/commission_attributes"

    def __init__(self, client: "BaseAsyncClient") -> None:
        super().__init__(client)
        self.criterias = AsyncCommissionAttributesCriteriasResource(client)
        self.relations = AsyncCommissionAttributesRelationsResource(client)


class AsyncCommissionPhasesResource(AsyncResource):
    _path = "/api/commission_phases"


class AsyncCommissionScopeTypesResource(AsyncResource):
    _path = "/api/commission_scope_types"


class AsyncCommissionShortcutsResource(AsyncResource):
    _path = "/api/commission_shortcuts"


class AsyncCommissionUsersResource(AsyncResource):
    _path = "/api/commission_users"


class AsyncCommissionsResource(AsyncResource):
    _path = "/api/commissions"

    def __init__(self, client: "BaseAsyncClient") -> None:
        super().__init__(client)
        self.attributes = AsyncCommissionAttributesResource(client)
        self.phases = AsyncCommissionPhasesResource(client)
        self.scope_types = AsyncCommissionScopeTypesResource(client)
        self.shortcuts = AsyncCommissionShortcutsResource(client)
        self.users = AsyncCommissionUsersResource(client)
