import time

import pytest

from usaspending_mcp.cache import Cache


@pytest.fixture
def cache():
    return Cache()

def test_cache_set_get_hit(cache):
    key = {"a": 1, "b": 2}
    value = "test_value"
    
    cache.set(key, value, ttl_seconds=60)
    
    result, hit = cache.get(key)
    assert hit is True
    assert result == value

def test_cache_miss_expired(cache):
    key = "expire_me"
    value = "foo"
    
    # Set with extremely short TTL
    cache.set(key, value, ttl_seconds=0.01)
    
    time.sleep(0.02)
    
    result, hit = cache.get(key)
    assert hit is False
    assert result is None

def test_cache_key_normalization(cache):
    # These two dicts are effectively same but defined with different key order
    key1 = {"a": 1, "b": 2}
    key2 = {"b": 2, "a": 1}
    value = "stable_key"
    
    cache.set(key1, value, ttl_seconds=60)
    
    result, hit = cache.get(key2)
    assert hit is True
    assert result == value

def test_cache_miss_unknown(cache):
    result, hit = cache.get("non_existent")
    assert hit is False
    assert result is None
