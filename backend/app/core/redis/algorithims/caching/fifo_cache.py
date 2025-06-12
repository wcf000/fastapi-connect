from collections.abc import MutableMapping

class FIFOCache(MutableMapping):
    """First-In-First-Out (FIFO) cache implementation."""
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = {}
        self.queue = []
    def __getitem__(self, key):
        return self.cache[key]
    def __setitem__(self, key, value):
        if key not in self.cache:
            if len(self.cache) >= self.capacity:
                oldest = self.queue.pop(0)
                del self.cache[oldest]
            self.queue.append(key)
        self.cache[key] = value
    def __delitem__(self, key):
        if key in self.cache:
            self.queue.remove(key)
            del self.cache[key]
    def __iter__(self):
        return iter(self.queue)
    def __len__(self):
        return len(self.cache)
    def get(self, key, default=None):
        return self.cache.get(key, default)
    def put(self, key, value):
        self.__setitem__(key, value)
