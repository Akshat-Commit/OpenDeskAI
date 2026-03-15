import pytest
import asyncio
from opendesk.utils.session_manager import create_session, is_session_valid, claim_session, SESSIONS

@pytest.fixture(autouse=True)
def cleanup_sessions():
    """Clear the SESSIONS dictionary before each test."""
    SESSIONS.clear()
    yield

async def test_session_lifecycle():
    """Tests the full lifecycle of a session (create -> valid -> claim -> valid)."""
    # 1. Create session
    token = create_session("https://test-url.com")
    assert token in SESSIONS
    assert is_session_valid(token) is True
    
    # 2. Claim session
    success = claim_session(token, 123456789)
    assert success is True
    assert SESSIONS[token]["claimed"] is True
    assert SESSIONS[token]["telegram_user_id"] == 123456789
    
    # 3. Stay valid after claim
    assert is_session_valid(token) is True

async def test_session_expiry():
    """Tests that unclaimed sessions expire after the timeout."""
    token = create_session("https://test-url.com")
    
    # Manually speed up time in the session object for testing
    SESSIONS[token]["expires_at"] = 0 
    
    assert is_session_valid(token) is False

async def test_session_claim_invalid_token():
    """Tests that claiming a non-existent token fails."""
    success = claim_session("invalid-token", 999)
    assert success is False

async def test_concurrent_session_creation():
    """Demo of an async test with actual await (though logic here is fast)."""
    # This is just to show we can use 'await' inside the tests
    tokens = await asyncio.gather(
        asyncio.to_thread(create_session, "url1"),
        asyncio.to_thread(create_session, "url2")
    )
    assert len(tokens) == 2
    assert tokens[0] != tokens[1]
    assert all(t in SESSIONS for t in tokens)
