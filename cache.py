import hashlib
from typing import Optional, Dict, Any

from cachetools import TTLCache


_cache: TTLCache = TTLCache(maxsize=256, ttl=300)


def _key(question: str) -> str:
    normalized = (question or "").strip().lower()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def get_cached(question: str) -> Optional[dict]:
    return _cache.get(_key(question))


def set_cached(question: str, result: Dict[str, Any]) -> None:
    _cache[_key(question)] = result


def cache_size() -> int:
    return len(_cache)

