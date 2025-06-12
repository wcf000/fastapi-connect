from typing import Any

class LIFOCache:
    """
    Last In, First Out (LIFO) cache.
    Evicts the most recently added entry when capacity is exceeded.
    """
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[Any, Any] = {}
        self.stack: list[Any] = []

    def get(self, key: Any) -> Any:
        return self.cache.get(key, -1)

    def put(self, key: Any, value: Any) -> None:
        if len(self.cache) >= self.capacity:
            newest_key = self.stack.pop()
            del self.cache[newest_key]
        self.cache[key] = value
        self.stack.append(key)
