
from ..dynamic import DynamicObject


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

        # Get public attributes (filter out private ones starting with '_')
        public_keys = [key for key in self.__dict__.keys() if not key.startswith('_')]

        if not public_keys:
            return f"<{cls} empty>"

        keys = ", ".join(public_keys)
        return f"<{cls} fields=[{keys}]>"