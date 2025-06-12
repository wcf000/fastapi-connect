# Redis Rate Limiter Fixture Strategy for Redis Rate Limiting Tests

This document explains the fixture strategy for robust and deterministic testing of Redis-backed rate limiting algorithms.

---

## Handling Timing and Type Issues in Async Redis Tests

### 1. **Timing Issues with Rate-Limiting Algorithms**

- **Symptom:** Tests fail intermittently, especially for token bucket or sliding window algorithms, due to async, Redis, or system timing jitter.
- **Root Cause:** Token refills or window resets are not perfectly aligned with test sleeps; some implementations refill tokens only on access.
- **Fix Pattern:**
    - Always use a unique key per test to avoid state bleed.
    - After draining a limiter, wait for the full refill interval **plus a small buffer** (e.g., `interval + 0.1s`).
    - After waiting, attempt to consume again in a loop, sleeping briefly between attempts, to allow for async/Redis lag.
    - For token bucket: Only one token is refilled per interval (unless `refill_rate > 1`). After refill, only one call should be allowed, then block again. Wait another interval for the next token.

#### Example (Token Bucket):
```python
# After draining the bucket...
await asyncio.sleep(refill_time + 0.1)
allowed = False
for _ in range(10):
    allowed = await algo_func(RedisCache(redis_client), **kwargs)
    if allowed:
        break
    await asyncio.sleep(0.2)
assert allowed, "Token bucket did not refill as expected."
# Only one call should be allowed per interval
allowed2 = await algo_func(RedisCache(redis_client), **kwargs)
assert not allowed2, "Token bucket should only allow one token per interval."
```

### 2. **Type Issues with Fixtures**

- **Symptom:** `TypeError`, `fixture not found`, or unexpected object types in tests.
- **Fix Pattern:**
    - Ensure all fixtures are defined in `conftest.py` and are properly named.
    - Use type hints for all fixtures and test parameters for clarity.
    - If using custom clients or mocks, ensure they match the expected interface of the production client.

#### Example (Fixture Signature):
```python
@pytest.fixture
def redis_client() -> redis.asyncio.Redis:
    ...
```

---

## Best Practices for Deterministic Redis Tests

- Always generate a unique key per test run (e.g., `f"test:{uuid.uuid4()}"`).
- Avoid strict single-attempt assertions for time-based logic; prefer retry loops.
- Add a buffer to sleep intervals to account for system/Redis lag.
- Use `pytest.mark.asyncio` or `pytest-asyncio` for all async tests.
- Document edge-case handling in test docstrings and comments.
- Clean up unused keys or flush test Redis DB between runs if needed.

---

## Troubleshooting Checklist
- [x] Are you using unique keys per test?
- [x] Are you waiting a full interval/window plus buffer before retrying?
- [x] Are you using retry loops for refill checks?
- [x] Are all fixtures correctly defined and type-hinted?
- [x] Are you testing the correct refill/blocking semantics for your algorithm?

---

## Robust Fixture Usage

- Use the `conftest.py` file to define all fixtures.
- Ensure fixtures are properly named and type-hinted.
- Use the `pytest.mark.asyncio` marker for all async tests.
- Use the `pytest.fixture` decorator to define fixtures.
    - The first two calls are allowed (limit=2).
    - The third call is blocked.
    - After waiting for the window/interval, the next call is allowed again.
  - **Throttle, Debounce:**
    - Only the first call is allowed per interval.
    - Subsequent calls within the interval are blocked.
    - After waiting for the interval, the next call is allowed again.
- **Fail-Open Guarantee:** If Redis is unavailable, all algorithms should allow requests (fail-open), and this is explicitly tested.

## Example Test Pattern

```
# For limit=2
allowed1 = await algo_func(...)
assert allowed1 is True
allowed2 = await algo_func(...)
assert allowed2 is True
allowed3 = await algo_func(...)
assert allowed3 is False
await asyncio.sleep(window)
allowed4 = await algo_func(...)
assert allowed4 is True
```

## Rationale

- Ensures the algorithms match their contract and are robust against Redis failures.
- Prevents false positives/negatives due to state leakage or incorrect test logic.

## See Also
- `conftest.py` for the Redis flush fixture
- Each algorithm's implementation for details on logic and edge cases
