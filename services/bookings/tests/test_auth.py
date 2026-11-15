import pytest

from database.database import get_connection, create_booking_tables
from bookings import auth, repository
from bookings.auth import AuthError


@pytest.fixture
def conn():
    c = get_connection(":memory:")
    create_booking_tables(c)
    yield c
    c.close()


def register_maya(conn, email="maya@example.com", password="secret123"):
    return auth.register(conn, "Maya", email, password)


def test_register_stores_hash_not_password(conn):
    member_id = register_maya(conn)
    stored = repository.get_member_by_id(conn, member_id)["password_hash"]
    assert stored != "secret123"
    assert "secret123" not in stored


def test_same_password_gets_different_hashes(conn):
    a = register_maya(conn, email="a@example.com")
    b = register_maya(conn, email="b@example.com")
    hash_a = repository.get_member_by_id(conn, a)["password_hash"]
    hash_b = repository.get_member_by_id(conn, b)["password_hash"]
    assert hash_a != hash_b


def test_duplicate_email_rejected_case_insensitive(conn):
    register_maya(conn, email="maya@example.com")
    with pytest.raises(AuthError):
        register_maya(conn, email="MAYA@Example.com")


@pytest.mark.parametrize("name,email,password", [
    ("", "maya@example.com", "secret123"),
    ("Maya", "not-an-email", "secret123"),
    ("Maya", "maya@example.com", "short"),
    ("Maya", "maya@example.com", None),
])
def test_invalid_registration_rejected(conn, name, email, password):
    with pytest.raises(AuthError):
        auth.register(conn, name, email, password)


def test_login_succeeds_and_hides_hash(conn):
    member_id = register_maya(conn)
    member = auth.login(conn, " Maya@Example.com ", "secret123")
    assert member["id"] == member_id
    assert "password_hash" not in member


def test_wrong_password_rejected(conn):
    register_maya(conn)
    with pytest.raises(AuthError):
        auth.login(conn, "maya@example.com", "wrongpass1")


def test_unknown_email_gives_same_error_as_wrong_password(conn):
    register_maya(conn)
    with pytest.raises(AuthError) as wrong_pw:
        auth.login(conn, "maya@example.com", "wrongpass1")
    with pytest.raises(AuthError) as no_user:
        auth.login(conn, "nobody@example.com", "secret123")
    assert str(wrong_pw.value) == str(no_user.value)


def test_get_member(conn):
    member_id = register_maya(conn)
    assert auth.get_member(conn, member_id)["email"] == "maya@example.com"
    assert auth.get_member(conn, 999) is None