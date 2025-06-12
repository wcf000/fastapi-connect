import pytest

@pytest.mark.asyncio
async def test_redis_fixture(redis_client):
    # Simple ping to verify fixture yields a working Redis client
    pong = await redis_client.ping()
    assert pong is True or pong == "PONG"
