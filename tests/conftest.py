"""Shared test fixtures."""
import pytest
import aiohttp
from aioresponses import aioresponses


@pytest.fixture
def mock_aiohttp():
    """Provide an aioresponses context for mocking HTTP."""
    with aioresponses() as m:
        yield m


@pytest.fixture
async def aiohttp_session():
    """Provide a real aiohttp session for use with aioresponses."""
    async with aiohttp.ClientSession() as session:
        yield session
