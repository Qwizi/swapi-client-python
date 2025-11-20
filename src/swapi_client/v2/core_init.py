from .models.core import CoreModel
from .queryset_core import CoreQuerySet


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