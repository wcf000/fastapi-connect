import heapq
import time

class LFUNode:
    def __init__(self, key, value, freq=1, timestamp=None):
        self.key = key
        self.value = value
        self.freq = freq
        self.timestamp = timestamp if timestamp is not None else time.monotonic()
    def __lt__(self, other):
        return (self.freq, self.timestamp) < (other.freq, other.timestamp)

class LFUCache:
    """Least Frequently Used (LFU) cache implementation."""
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = {}  # key -> LFUNode
        self.heap = []   # min-heap of LFUNode
        self.time = 0    # logical clock for tie-breaking
    def get(self, key):
        node = self.cache.get(key)
        if not node:
            return -1
        node.freq += 1
        self.time += 1
        node.timestamp = self.time
        heapq.heapify(self.heap)
        return node.value
    def put(self, key, value):
        if self.capacity == 0:
            return
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            node.freq += 1
            self.time += 1
            node.timestamp = self.time
        else:
            if len(self.cache) >= self.capacity:
                while self.heap:
                    lfu = heapq.heappop(self.heap)
                    if lfu.key in self.cache and self.cache[lfu.key] is lfu:
                        del self.cache[lfu.key]
                        break
            node = LFUNode(key, value, freq=1, timestamp=self.time)
            self.cache[key] = node
            self.time += 1
        heapq.heappush(self.heap, self.cache[key])
