# Redis Sharding Implementation Guide

## Configuration

```python
# In config.py
REDIS_SHARD_SIZE = 25 * 1024 * 1024 * 1024  # 25GB per shard
REDIS_SHARD_OPS_LIMIT = 25000  # Operations/second limit
REDIS_SHARD_NODES = [
    {"host": "shard1", "port": 6379},
    {"host": "shard2", "port": 6379}
]
```

## Key Distribution

- Uses consistent hashing via RedisCluster
- Keys distributed evenly across shards
- Automatic rebalancing when adding/removing nodes

## Monitoring

```bash
# Check shard sizes
redis-cli --bigkeys

# Check ops/sec per shard
redis-cli info stats | grep instantaneous_ops
```

## Best Practices
- Keep shards under 25GB
- Monitor ops/sec per shard
- Add shards before hitting limits
- Use `redis-cli --hotkeys` to identify hot partitions
