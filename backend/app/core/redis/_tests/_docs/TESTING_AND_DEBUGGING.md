# Redis Rate Limiter & Sharding Test Suite: Testing & Debugging Guide

## How to Run the Tests

### 1. **Ensure Redis is Running**
- The test suite expects a local Redis instance (or Docker container) to be running.
- The `conftest.py` fixtures will attempt to start Redis via Docker Compose if not already running.
- **Docker Compose file:** `app/core/redis/docker/docker-compose.local.yml`

### 2. **Running All Tests**
From the `backend` directory:
```bash
poetry run pytest app/core/redis/_tests/
```

### 3. **Running a Specific Test File**
```bash
poetry run pytest app/core/redis/_tests/test_algorithms.py
poetry run pytest app/core/redis/_tests/test_sharding.py
```

### 4. **Test Output & Warnings**
- Pytest will show assertion failures, warnings, and logs.
- You may see warnings about fixture scopes or coroutine warnings if fixtures or test signatures are misused.

---

## Common Debugging Steps & What We've Tried

### **Fixture Issues: async_generator instead of client**
- **Symptom:** Errors like `'async_generator' object has no attribute 'incr'`, `'pipeline'`, or `'eval'`.
- **Root Cause:** The `redis_client` fixture must yield the actual Redis client, not a generator. Do **not** call or await the fixture in your test; let pytest inject it.
- **Fix:**
  - Use this pattern in your test:
    ```python
    async def test_x(redis_client):
        await redis_client.set("foo", "bar")
    ```
  - Do **not** do:
    ```python
    client = redis_client()  # WRONG
    ```

### **Fail-Open Logic Always Triggering**
- If you see warnings like `Redis unavailable, allowing event (fail-open): ...`, it means your test is not using a real Redis client.
- Double-check your fixture and test signatures.

### **Lint & Import Issues**
- Ruff and Pyright may warn about unused/redundant imports or imports not at the top of the file.
- Clean up imports and sort them for best practices.

### **Test Isolation**
- The suite flushes Redis between tests for isolation (see `flush_redis` fixture).
- If you see data leakage, ensure the flush is being awaited properly.

---

## Troubleshooting Checklist
- [ ] Is Redis running and healthy? (`docker ps`, `docker logs redis`)
- [ ] Are you using the `redis_client` fixture as a parameter, not calling it?
- [ ] Are all rate limiter/sharding functions using dependency injection (`RedisCache(redis_client)`)?
- [ ] Are there any warnings about async generators or missing attributes?
- [ ] Are all imports at the top and sorted?
- [ ] Are tests isolated (no data leakage between runs)?

---

## Example Test Pattern
```python
@pytest.mark.asyncio
async def test_my_feature(redis_client):
    await redis_client.set("foo", "bar")
    value = await redis_client.get("foo")
    assert value == "bar"
```

---

## What We've Tried
- Refactored all rate limiter functions to accept a `RedisCache` instance (DI pattern).
- Ensured all tests use the async `redis_client` fixture.
- Fixed fixture bugs where the generator was being passed instead of the client.
- Cleaned up unused imports and sorted import blocks.
- Added better-comments for maintainability and clarity.

---

## If You Get Stuck
- Double-check the fixture and test signatures.
- Check logs for fail-open warnings.
- Ask for help with the exact error message and test code snippet.

---

*Last updated: 2025-05-11*
