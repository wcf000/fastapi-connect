from typing import Any

class MRUCache:
    """
    Most Recently Used (MRU) cache.
    Evicts the most recently accessed entry when capacity is exceeded.
    """
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[Any, Any] = {}
        self.stack: list[Any] = []

    def get(self, key: Any) -> Any:
        if key in self.cache:
            self.stack.remove(key)
            self.stack.append(key)
            return self.cache[key]
        return -1

    def put(self, key: Any, value: Any) -> None:
        if key in self.cache:
            self.stack.remove(key)
        elif len(self.cache) >= self.capacity:
            most_recently_used_key = self.stack.pop()
            del self.cache[most_recently_used_key]
        self.cache[key] = value
        self.stack.append(key)
