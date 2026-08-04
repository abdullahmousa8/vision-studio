from uuid import uuid4

from app.services.auth_service import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_roundtrip():
    hashed = hash_password("super-secret")
    assert hashed != "super-secret"
    assert verify_password("super-secret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_password_hashing_is_salted():
    assert hash_password("same") != hash_password("same")


def test_token_roundtrip():
    uid = uuid4()
    token, expires_in = create_access_token(uid)
    assert expires_in == 60
    assert decode_token(token) == uid
