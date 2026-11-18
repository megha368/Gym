"""Login tokens.

When a member logs in, Bookings gives the browser a token: their member id, signed with
SECRET_KEY. The UI sends it back on every request in the header
    Authorization: Bearer <token>
Because it is signed, nobody can change the member id inside it or make one up without
knowing SECRET_KEY. Tokens stop working after TOKEN_MAX_AGE_S.

Why a token and not Flask's session cookie (Assignment 1): the UI and Bookings are on
different websites, and browsers block or restrict cookies sent between different sites.
"""

from itsdangerous import BadSignature, URLSafeTimedSerializer

from config.settings import SECRET_KEY

TOKEN_MAX_AGE_S = 7 * 24 * 3600  # one week

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="login-token")


def create_token(member_id):
    return _serializer.dumps({"member_id": member_id})


def read_token(token):
    """The member id inside a valid token, or None if it is invalid, tampered with or expired."""
    try:
        return _serializer.loads(token, max_age=TOKEN_MAX_AGE_S)["member_id"]
    except (BadSignature, KeyError, TypeError):
        return None
