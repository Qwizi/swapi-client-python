from typing import Any, Dict, List, Optional, Union


class SWQueryBuilder:
    """
    Helper class to build complex SW API query parameters.
    
    Enhanced filtering capabilities:
    - Basic filtering: filter("name", "value") -> filter[name][eq]=value
    - Operator filtering: filter("age", 18, "gte") -> filter[age][gte]=18  
    - Nested filtering: filter(["attributes", "476"], "some text", "hasText") 
                       -> filter[attributes][476][hasText]=some text
    - Complex OR filters: filter_or({("attributes", "476"): {"hasText": "text"}})
                         -> filterOr[0][attributes][476][hasText]=text
    - Complex AND filters: filter_and({("nested", "field"): "value"})
                          -> filterAnd[0][nested][field][eq]=value
    
    Note: Operator is always placed at the end of the filter structure for consistency.
    Supported operators: eq, ne, gt, lt, gte, lte, in, notIn, like, ilike, notLike, 
                        isNull, isNotNull, hasText, and more.
    """

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
        self, 
        field: Union[str, List[str]], 
        value: Any = None, 
        operator: str = "eq"
    ) -> "SWQueryBuilder":
        """
        Add filter parameter with support for nested field paths.
        
        Args:
            field: Field name as string or list of nested field names.
                   Examples: 
                   - "name" -> filter[name][operator]
                   - ["attributes", "476"] -> filter[attributes][476][operator]
            value: The value to filter by
            operator: The operator to use (eq, ne, gt, lt, gte, lte, in, notIn, 
                     like, ilike, notLike, isNull, isNotNull, hasText, etc.)
        """
        # Build the field path
        if isinstance(field, list):
            field_path = "][".join(field)
            filter_key = f"filter[{field_path}]"
        else:
            filter_key = f"filter[{field}]"
        
        # Always add operator at the end for consistency
        if operator in ["isNull", "isNotNull"]:
            self.params[f"{filter_key}[{operator}]"] = ""
        else:
            self.params[f"{filter_key}[{operator}]"] = (
                str(value)
                if not isinstance(value, list)
                else ",".join(map(str, value))
            )
        return self

    def filter_or(
        self, filters: Dict[Union[str, tuple], Any], group_index: int = 0
    ) -> "SWQueryBuilder":
        """
        Add filterOr parameters with support for nested field paths.
        
        Args:
            filters: Dictionary where keys can be:
                    - Simple field names (str): "name"
                    - Nested field tuples: ("attributes", "476", "hasText")
                    Values can be:
                    - Simple values for equality comparison
                    - Dict with operator and value: {"hasText": "some_value"}
            group_index: The OR group index
        """
        for field, filter_config in filters.items():
            # Build field path
            if isinstance(field, tuple):
                field_path = "][".join(field)
                base_key = f"filterOr[{group_index}][{field_path}]"
            else:
                base_key = f"filterOr[{group_index}][{field}]"
            
            if isinstance(filter_config, dict):
                for operator, value in filter_config.items():
                    if operator in ["isNull", "isNotNull"]:
                        self.params[f"{base_key}[{operator}]"] = ""
                    else:
                        filter_value = (
                            str(value)
                            if not isinstance(value, list)
                            else ",".join(map(str, value))
                        )
                        self.params[f"{base_key}[{operator}]"] = filter_value
            else:
                # For simple values, default to 'eq' operator
                self.params[f"{base_key}[eq]"] = str(filter_config)
        return self

    def filter_and(
        self, filters: Dict[Union[str, tuple], Any], group_index: int = 0
    ) -> "SWQueryBuilder":
        """
        Add filterAnd parameters with support for nested field paths.
        
        Args:
            filters: Dictionary where keys can be:
                    - Simple field names (str): "name"
                    - Nested field tuples: ("attributes", "476")
                    Values can be:
                    - Simple values for equality comparison
                    - Dict with operator and value: {"hasText": "some_value"}
            group_index: The AND group index
        """
        for field, filter_config in filters.items():
            # Build field path
            if isinstance(field, tuple):
                field_path = "][".join(field)
                base_key = f"filterAnd[{group_index}][{field_path}]"
            else:
                base_key = f"filterAnd[{group_index}][{field}]"
            
            if isinstance(filter_config, dict):
                for operator, value in filter_config.items():
                    if operator in ["isNull", "isNotNull"]:
                        self.params[f"{base_key}[{operator}]"] = ""
                    else:
                        filter_value = (
                            str(value)
                            if not isinstance(value, list)
                            else ",".join(map(str, value))
                        )
                        self.params[f"{base_key}[{operator}]"] = filter_value
            else:
                # For simple values, default to 'eq' operator
                self.params[f"{base_key}[eq]"] = str(filter_config)
        return self

    def filter_nested(
        self, 
        field_path: str, 
        value: Any = None, 
        operator: str = "eq"
    ) -> "SWQueryBuilder":
        """
        Convenience method for creating nested filters using dot notation.
        
        Args:
            field_path: Dot-separated field path like "attributes.476"
            value: The value to filter by
            operator: The operator to use
            
        Example:
            filter_nested("attributes.476", "some text", "hasText")
            -> filter[attributes][476][hasText]=some text
        """
        field_list = field_path.split(".")
        return self.filter(field_list, value, operator)

    def build(self) -> Dict[str, str]:
        """Build and return the query parameters"""
        return self.params.copy()
