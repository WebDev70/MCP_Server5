import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple


class Cache:
    def __init__(self):
        self._store: Dict[str, Tuple[Any, float]] = {}

    def _normalize_key(self, key_data: Any) -> str:
        """
        Generates a stable string hash for the cache key.
        Handles dict key sorting to ensure stability.
        """
        try:
            # Sort keys for consistent JSON representation
            serialized = json.dumps(key_data, sort_keys=True, default=str)
            return hashlib.md5(serialized.encode("utf-8")).hexdigest()
        except TypeError:
            # Fallback for non-JSON serializable objects (use str repr)
            return hashlib.md5(str(key_data).encode("utf-8")).hexdigest()

    def get(self, key_data: Any) -> Tuple[Optional[Any], bool]:
        """
        Retrieves data from cache if it exists and hasn't expired.
        Returns (data, cache_hit_boolean)
        """
        key = self._normalize_key(key_data)
        if key in self._store:
            data, expiry = self._store[key]
            if time.time() < expiry:
                return data, True
            else:
                # Cleanup expired item
                del self._store[key]
        return None, False

    def set(self, key_data: Any, value: Any, ttl_seconds: int = 300) -> None:
        """
        Stores data in cache with a TTL.
        """
        key = self._normalize_key(key_data)
        expiry = time.time() + ttl_seconds
        self._store[key] = (value, expiry)

    def clear(self) -> None:
        """Clears the entire cache."""
        self._store.clear()