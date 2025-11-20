
from ..dynamic import DynamicObject
from ..queryset_core import CoreQuerySet


class CoreModel(DynamicObject):
    """
    Uniwersalny model dla endpointów Core API.
    Wszystkie pola są dynamiczne — tak jak w CommissionModel.
    """

    def __init__(self, data: dict):
        super().__init__(data)

    @property
    def pk(self):
        return getattr(self, "id", None)

    def __repr__(self):
        cls = self.__class__.__name__

        # DynamicObject może mieć _raw lub _data
        raw = getattr(self, "_raw", None)
        data = getattr(self, "_data", None)

        mapping = raw if isinstance(raw, dict) else data

        if not mapping:
            return f"<{cls} empty>"

        keys = ", ".join(mapping.keys())
        return f"<{cls} fields=[{keys}]>"
    

class Core:
    """
    Główna entry-point dla prostych endpointów typu:
    /api/me
    /api/home
    /api/settings
    /api/modules
    /api/user/profile
    itd.
    """

    client = None  # identycznie jak Commission.client

    @classmethod
    def objects(cls) -> CoreQuerySet:
        if cls.client is None:
            raise RuntimeError("Core.client must be assigned with SWAPIClient.")
        return CoreQuerySet(cls.client, CoreModel)