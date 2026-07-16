"""Cache theo request và TTL RAM ngắn cho warm instance Vercel."""
import time
from threading import Lock
from flask import g, has_request_context

def cache_get(key):
    if not has_request_context():
        return None
    return getattr(g, key, None)

def cache_set(key, value):
    if has_request_context():
        setattr(g, key, value)
    return value

def cache_delete(key):
    if has_request_context() and hasattr(g, key):
        delattr(g, key)

_ttl_cache = {}
_ttl_cache_lock = Lock()

def ttl_cache_get(key):
    now = time.monotonic()
    with _ttl_cache_lock:
        item = _ttl_cache.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at <= now:
            _ttl_cache.pop(key, None)
            return None
        return value

def ttl_cache_set(key, value, ttl_seconds):
    with _ttl_cache_lock:
        _ttl_cache[key] = (time.monotonic() + max(0.1, float(ttl_seconds)), value)
    return value

def ttl_cache_delete(*keys):
    with _ttl_cache_lock:
        for key in keys:
            _ttl_cache.pop(key, None)
