"""The Bookings API. Every endpoint takes and returns JSON.

Endpoints marked "login required" need the header  Authorization: Bearer <token>,
where the token comes from POST /auth/register or POST /auth/login.
"""

from functools import wraps

from flask import Blueprint, g, request

from bookings import auth, service, tokens
from bookings.auth import AuthError
from bookings.commands import BookCommand, CancelCommand, run_command
from bookings.service import BookingError

bp = Blueprint("api", __name__)

MAX_SESSION_IDS = 200  # upper limit for one /availability request


# ---------- helpers ----------

def _body():
    """The request's JSON body as a dict ({} if missing or not JSON)."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _current_member():
    """The logged-in member from the Authorization header, or None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    member_id = tokens.read_token(header[len("Bearer "):])
    return auth.get_member(g.conn, member_id) if member_id else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        g.member = _current_member()
        if g.member is None:
            return {"error": "Please log in first."}, 401
        return view(*args, **kwargs)

    return wrapped


@bp.errorhandler(AuthError)
@bp.errorhandler(BookingError)
def rule_broken(error):
    """A business rule said no (wrong password, class full and no pass, ...)."""
    return {"error": str(error)}, 400


def _logged_in(member):
    return {"token": tokens.create_token(member["id"]), "member": member}


# ---------- accounts ----------

@bp.post("/auth/register")
def register():
    data = _body()
    member_id = auth.register(g.conn, data.get("name"), data.get("email"), data.get("password"))
    return _logged_in(auth.get_member(g.conn, member_id)), 201


@bp.post("/auth/login")
def login():
    data = _body()
    return _logged_in(auth.login(g.conn, data.get("email"), data.get("password")))


@bp.get("/me")
@login_required
def me():
    return {"member": g.member}


# ---------- schedule (Bookings' half) ----------

@bp.get("/availability")
def availability():
    """GET /availability?session_ids=1,2,3 -> spots taken per session, and this member's
    status if logged in. Login optional."""
    try:
        session_ids = [int(x) for x in request.args.get("session_ids", "").split(",") if x.strip()]
    except ValueError:
        return {"error": "session_ids must be a comma-separated list of numbers"}, 400
    if len(session_ids) > MAX_SESSION_IDS:
        return {"error": f"At most {MAX_SESSION_IDS} session ids per request"}, 400
    member = _current_member()
    result = service.get_availability(g.conn, session_ids, member["id"] if member else None)
    return {"sessions": {str(k): v for k, v in result.items()}}


# ---------- bookings and waitlist ----------

@bp.post("/bookings")
@login_required
def book():
    """Book a session, or join its waitlist if it's full. Crosses the seam: asks
    Scheduling whether the session exists, is open, and its capacity."""
    session_id = _body().get("session_id")
    if not isinstance(session_id, int):
        return {"error": "session_id (a number) is required"}, 400
    result = run_command(g.conn, BookCommand(g.member["id"], session_id))
    return result, 201


@bp.get("/bookings")
@login_required
def my_bookings():
    """This member's bookings and waitlist entries, with class details from Scheduling.
    If Scheduling is down, they're still listed, without details (details_missing)."""
    bookings = service.list_member_bookings(g.conn, g.member["id"])
    waitlist = service.list_member_waitlist(g.conn, g.member["id"])
    return {
        "bookings": bookings,
        "waitlist": waitlist,
        "details_missing": not all(item["details_available"] for item in bookings + waitlist),
    }


@bp.post("/bookings/<int:booking_id>/cancel")
@login_required
def cancel(booking_id):
    result = run_command(g.conn, CancelCommand(g.member["id"], booking_id))
    return {"booking_id": booking_id, "promoted": result["promoted"] is not None}


@bp.delete("/waitlist/<int:session_id>")
@login_required
def leave_waitlist(session_id):
    service.leave_waitlist(g.conn, g.member["id"], session_id)
    return {"session_id": session_id, "left": True}


# ---------- passes ----------

@bp.get("/passes")
@login_required
def passes():
    return {"passes": service.list_member_passes(g.conn, g.member["id"])}


@bp.post("/passes")
@login_required
def buy_pass():
    pass_id = service.buy_pass(g.conn, g.member["id"], _body().get("pass_type"))
    return {"pass_id": pass_id}, 201
