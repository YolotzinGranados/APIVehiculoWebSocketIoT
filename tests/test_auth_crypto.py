import time

import pytest

from app.core.auth_crypto import (
    create_access_token, decode_access_token, hash_password,
    hash_refresh_token, verify_password,
)


def test_password_hash_and_verify():
    encoded = hash_password("UnaClaveSegura2026")
    assert encoded != "UnaClaveSegura2026"
    assert verify_password("UnaClaveSegura2026", encoded)
    assert not verify_password("OtraClave2026", encoded)


def test_access_token_round_trip():
    token = create_access_token(user_id=17, email="persona@example.com",
                                roles=["guest"], secret="x" * 48, ttl_seconds=60)
    claims = decode_access_token(token, "x" * 48)
    assert claims["sub"] == "17"
    assert claims["roles"] == ["guest"]


def test_access_token_rejects_wrong_secret():
    token = create_access_token(user_id=17, email="persona@example.com",
                                roles=["guest"], secret="x" * 48, ttl_seconds=60)
    with pytest.raises(ValueError):
        decode_access_token(token, "y" * 48)


def test_refresh_hash_is_one_way_and_deterministic():
    raw = "random-refresh-token"
    assert hash_refresh_token(raw) == hash_refresh_token(raw)
    assert hash_refresh_token(raw) != raw
