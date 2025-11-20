class DynamicObject:
    """
    Wrapper na dict, który pozwala na dostęp przez dot notation:
        obj.field
    oraz:
        obj.deep.field.value
    """

    def __init__(self, data: dict):
        for key, value in data.items():
            setattr(self, key, self._wrap(value))

    def _wrap(self, value):
        if isinstance(value, dict):
            return DynamicObject(value)
        if isinstance(value, list):
            return DynamicList(value)
        return value

    def to_dict(self):
        """
        Rekurencyjnie konwertuje obiekt do dict.
        """
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, DynamicObject):
                result[key] = value.to_dict()
            elif isinstance(value, DynamicList):
                result[key] = value.to_list()
            else:
                result[key] = value
        return result

    def __repr__(self):
        return f"DynamicObject({self.__dict__})"


class DynamicList(list):
    """
    Wrapper na listę, automatycznie konwertujący elementy dict → DynamicObject.
    """

    def __init__(self, data: list):
        super().__init__(self._wrap(item) for item in data)

    def _wrap(self, value):
        if isinstance(value, dict):
            return DynamicObject(value)
        if isinstance(value, list):
            return DynamicList(value)
        return value

    def to_list(self):
        return [
            item.to_dict() if isinstance(item, DynamicObject)
            else item.to_list() if isinstance(item, DynamicList)
            else item
            for item in self
        ]