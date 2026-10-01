import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

from bookings import repository

MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    """Raised when registration or login fails."""


def _public_view(member_row):
    """Member data that is safe to hand to the web layer (no password hash)."""
    return {
        "id": member_row["id"],
        "name": member_row["name"],
        "email": member_row["email"],
    }


def register(conn, name, email, password):
    name = (name or "").strip()
    email = (email or "").strip().lower()

    if not name:
        raise AuthError("Name is required")
    if "@" not in email:
        raise AuthError("A valid email is required")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")

    password_hash = generate_password_hash(password)
    try:
        return repository.add_member(conn, name, email, password_hash)
    except sqlite3.IntegrityError:
        raise AuthError("An account with this email already exists")


def login(conn, email, password):
    email = (email or "").strip().lower()
    member = repository.get_member_by_email(conn, email)

    # Same message for "no such email" and "wrong password", so an attacker
    # can't use the error to find out which emails have accounts.
    if member is None or not check_password_hash(member["password_hash"], password or ""):
        raise AuthError("Invalid email or password")

    return _public_view(member)


def get_member(conn, member_id):
    member = repository.get_member_by_id(conn, member_id)
    return _public_view(member) if member else None