from typing import Any, Dict, List, Optional


class SWQueryBuilder:
    """Helper class to build complex SW API query parameters"""

    def __init__(self):
        self.params = {}

    def with_relations(self, value: bool = True) -> "SWQueryBuilder":
        """Set with_relations parameter"""
        self.params["setting[with_relations]"] = str(value).lower()
        return self

    def with_editable_settings_for_action(
        self, action: Optional[str] = None
    ) -> "SWQueryBuilder":
        """Set with_editable_settings_for_action parameter"""
        self.params["setting[with_editable_settings_for_action]"] = action or "null"
        return self

    def with_cache(self, value: bool = False) -> "SWQueryBuilder":
        """Set with_cache parameter (deprecated)"""
        self.params["setting[with_cache]"] = str(value).lower()
        return self

    def limit_to_my_settings(self, value: bool = True) -> "SWQueryBuilder":
        """Set limit_to_my_settings parameter"""
        self.params["setting[limit_to_my_settings]"] = str(value).lower()
        return self

    def lang(self, language: str = "pl") -> "SWQueryBuilder":
        """Set language parameter"""
        self.params["setting[lang]"] = language
        return self

    def fields(self, field_list: List[str]) -> "SWQueryBuilder":
        """Set fields to include in response"""
        self.params["fields"] = ",".join(field_list)
        return self

    def extra_fields(self, field_list: List[str]) -> "SWQueryBuilder":
        """Set extra fields to include in response"""
        self.params["extra_fields"] = ",".join(field_list)
        return self

    def for_metadata(self, fields: Dict[str, Any]) -> "SWQueryBuilder":
        """
        Determines for which field values the meta data will be returned.
        Simulates an object change to get metadata for specific values.
        """
        for field, value in fields.items():
            self.params[f"for[{field}]"] = str(value)
        return self

    def order(self, field: str, direction: str = "asc") -> "SWQueryBuilder":
        """Add ordering parameter"""
        self.params[f"order[{field}]"] = direction
        return self

    def page_limit(self, limit: int = 20) -> "SWQueryBuilder":
        """Set page limit"""
        self.params["page[limit]"] = str(limit)
        return self

    def page_offset(self, offset: int) -> "SWQueryBuilder":
        """Set page offset"""
        self.params["page[offset]"] = str(offset)
        return self

    def page_number(self, number: int = 1) -> "SWQueryBuilder":
        """Set page number"""
        self.params["page[number]"] = str(number)
        return self

    def filter(
        self, field: str, value: Any = None, operator: str = "eq"
    ) -> "SWQueryBuilder":
        """Add filter parameter"""
        if operator in ["isNull", "isNotNull"]:
            self.params[f"filter[{field}][{operator}]"] = ""
        elif operator == "eq":
            self.params[f"filter[{field}]"] = str(value)
        else:
            self.params[f"filter[{field}][{operator}]"] = (
                str(value)
                if not isinstance(value, list)
                else ",".join(map(str, value))
            )
        return self

    def filter_or(
        self, filters: Dict[str, Any], group_index: int = 0
    ) -> "SWQueryBuilder":
        """Add filterOr parameters"""
        for field, filter_config in filters.items():
            if isinstance(filter_config, dict):
                for operator, value in filter_config.items():
                    if operator in ["isNull", "isNotNull"]:
                        self.params[f"filterOr[{group_index}][{field}][{operator}]"] = ""
                    else:
                        filter_value = (
                            str(value)
                            if not isinstance(value, list)
                            else ",".join(map(str, value))
                        )
                        self.params[
                            f"filterOr[{group_index}][{field}][{operator}]"
                        ] = filter_value
            else:
                self.params[f"filterOr[{group_index}][{field}]"] = str(filter_config)
        return self

    def filter_and(
        self, filters: Dict[str, Any], group_index: int = 0
    ) -> "SWQueryBuilder":
        """Add filterAnd parameters"""
        for field, filter_config in filters.items():
            if isinstance(filter_config, dict):
                for operator, value in filter_config.items():
                    if operator in ["isNull", "isNotNull"]:
                        self.params[
                            f"filterAnd[{group_index}][{field}][{operator}]"
                        ] = ""
                    else:
                        filter_value = (
                            str(value)
                            if not isinstance(value, list)
                            else ",".join(map(str, value))
                        )
                        self.params[
                            f"filterAnd[{group_index}][{field}][{operator}]"
                        ] = filter_value
            else:
                self.params[f"filterAnd[{group_index}][{field}]"] = str(filter_config)
        return self

    def build(self) -> Dict[str, str]:
        """Build and return the query parameters"""
        return self.params.copy()
