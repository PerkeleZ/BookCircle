"""Кэш чтения с версионированием: инвалидация = увеличить версию пространства имён (работает и с Redis, и с LocMem)."""
from django.core.cache import cache


def version(ns):
    v = cache.get(f'v:{ns}')
    if v is None:
        cache.set(f'v:{ns}', 1, None)
        v = 1
    return v


def bump(ns):
    try:
        cache.incr(f'v:{ns}')
    except ValueError:
        cache.set(f'v:{ns}', 2, None)


def cached(ns, key, ttl, producer):
    full = f'{ns}:{version(ns)}:{key}'
    value = cache.get(full)
    if value is None:
        value = producer()
        cache.set(full, value, ttl)
    return value
