#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced filtering capabilities of SWQueryBuilder.
"""

from src.swapi_client.query_builder import SWQueryBuilder


def test_basic_filtering():
    """Test basic filtering functionality (backward compatibility)"""
    print("=== Testing Basic Filtering ===")
    
    builder = SWQueryBuilder()
    params = (builder
              .filter("name", "John")
              .filter("age", 18, "gte")
              .filter("status", operator="isNotNull")
              .build())
    
    print("Basic filters:")
    for key, value in params.items():
        print(f"  {key} = {value}")
    print()


def test_nested_filtering():
    """Test the new nested filtering functionality"""
    print("=== Testing Nested Filtering ===")
    
    builder = SWQueryBuilder()
    params = (builder
              .filter(["attributes", "476", "hasText"], "some text")
              .filter(["metadata", "user", "id"], 123)
              .filter(["config", "settings", "enabled"], True, "eq")
              .build())
    
    print("Nested filters:")
    for key, value in params.items():
        print(f"  {key} = {value}")
    print()


def test_convenience_method():
    """Test the convenience filter_nested method"""
    print("=== Testing Convenience Method ===")
    
    builder = SWQueryBuilder()
    params = (builder
              .filter_nested("attributes.476.hasText", "some text")
              .filter_nested("metadata.user.name", "John", "like")
              .build())
    
    print("Convenience method filters:")
    for key, value in params.items():
        print(f"  {key} = {value}")
    print()


def test_complex_or_filtering():
    """Test enhanced OR filtering with nested fields"""
    print("=== Testing Complex OR Filtering ===")
    
    builder = SWQueryBuilder()
    params = (builder
              .filter_or({
                  ("attributes", "476", "hasText"): {"like": "some text"},
                  ("metadata", "status"): "active",
                  "name": {"ne": "test"}
              }, group_index=0)
              .build())
    
    print("Complex OR filters:")
    for key, value in params.items():
        print(f"  {key} = {value}")
    print()


def test_complex_and_filtering():
    """Test enhanced AND filtering with nested fields"""
    print("=== Testing Complex AND Filtering ===")
    
    builder = SWQueryBuilder()
    params = (builder
              .filter_and({
                  ("attributes", "476", "hasText"): {"hasText": ""},
                  ("config", "enabled"): True,
                  "created_at": {"gte": "2024-01-01"}
              }, group_index=0)
              .build())
    
    print("Complex AND filters:")
    for key, value in params.items():
        print(f"  {key} = {value}")
    print()


def test_combined_filtering():
    """Test combining all filter types"""
    print("=== Testing Combined Filtering ===")
    
    builder = SWQueryBuilder()
    params = (builder
              .filter("name", "John")  # Basic filter
              .filter(["attributes", "476", "hasText"], "text")  # Nested filter
              .filter_nested("metadata.user.id", 123)  # Convenience method
              .filter_or({
                  ("status", "active"): True,
                  "type": {"in": ["user", "admin"]}
              })  # OR filter with nested and simple
              .filter_and({
                  ("permissions", "read"): True,
                  "verified": True
              })  # AND filter
              .page_limit(50)  # Other query builder methods still work
              .build())
    
    print("Combined filters:")
    for key, value in sorted(params.items()):
        print(f"  {key} = {value}")
    print()


if __name__ == "__main__":
    test_basic_filtering()
    test_nested_filtering()
    test_convenience_method()
    test_complex_or_filtering()
    test_complex_and_filtering()
    test_combined_filtering()
    
    print("✅ All tests completed successfully!")
    print("\nExample usage for your specific case:")
    print("filter(['attributes', '476', 'hasText'], 'some_value') -> filter[attributes][476][hasText][eq]=some_value")
    print("OR")  
    print("filter_nested('attributes.476.hasText', 'some_value') -> filter[attributes][476][hasText][eq]=some_value")
    print("\nWith different operator:")
    print("filter(['attributes', '476', 'hasText'], 'some_value', 'like') -> filter[attributes][476][hasText][like]=some_value")