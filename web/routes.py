# Routes are Flask functions attached to web addresses (/login, /schedule, /bookings). 
# Each one reads what the user submitted, calls your services, and decides what to show next.

from datetime import datetime
from functools import wraps
from itertools import groupby

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from bookings import auth, service
from bookings.auth import AuthError
from bookings.commands import BookCommand, CancelCommand, run_command
from bookings.service import BookingError

bp = Blueprint("web", __name__)


# ---------- small helpers for the templates ----------

@bp.app_template_filter("pretty_day")
def pretty_day(value):
    return datetime.fromisoformat(value).strftime("%A, %d %B")


@bp.app_template_filter("pretty_time")
def pretty_time(value):
    return datetime.fromisoformat(value).strftime("%a %d %b, %H:%M")


@bp.app_template_filter("clock")
def clock(value):
    return datetime.fromisoformat(value).strftime("%H:%M")


@bp.app_template_filter("short_date")
def short_date(value):
    return datetime.fromisoformat(value).strftime("%d %b %Y")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.member is None:
            flash("Please log in first.", "error")
            return redirect(url_for("web.login"))
        return view(*args, **kwargs)

    return wrapped


# ---------- accounts ----------

@bp.route("/")
def home():
    return redirect(url_for("web.schedule"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            member_id = auth.register(
                g.conn,
                request.form.get("name"),
                request.form.get("email"),
                request.form.get("password"),
            )
        except AuthError as error:
            flash(str(error), "error")
        else:
            session.clear()
            session["member_id"] = member_id
            flash("Welcome! Your account is ready.", "success")
            return redirect(url_for("web.schedule"))
    return render_template("register.html", form=request.form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            member = auth.login(
                g.conn, request.form.get("email"), request.form.get("password")
            )
        except AuthError as error:
            flash(str(error), "error")
        else:
            session.clear()
            session["member_id"] = member["id"]
            return redirect(url_for("web.schedule"))
    return render_template("login.html", form=request.form)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("web.schedule"))


# ---------- schedule and bookings ----------

@bp.route("/schedule")
def schedule():
    member_id = g.member["id"] if g.member else None
    sessions = service.get_schedule(g.conn, member_id)
    days = [
        (day, list(items))
        for day, items in groupby(sessions, key=lambda s: s["start_time"][:10])
    ]
    return render_template("schedule.html", days=days)


@bp.route("/book/<int:session_id>", methods=["POST"])
@login_required
def book(session_id):
    try:
        result = run_command(g.conn, BookCommand(g.member["id"], session_id))
    except BookingError as error:
        flash(str(error), "error")
    else:
        if result["status"] == "confirmed":
            flash("Booked! See you there.", "success")
        else:
            flash(
                f"The class is full, so you are #{result['position']} on the waitlist.",
                "success",
            )
    return redirect(url_for("web.schedule"))


@bp.route("/bookings")
@login_required
def my_bookings():
    member_id = g.member["id"]
    return render_template(
        "bookings.html",
        bookings=service.list_member_bookings(g.conn, member_id),
        waitlist=service.list_member_waitlist(g.conn, member_id),
        passes=service.list_member_passes(g.conn, member_id),
    )


@bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel(booking_id):
    try:
        run_command(g.conn, CancelCommand(g.member["id"], booking_id))
    except BookingError as error:
        flash(str(error), "error")
    else:
        flash("Booking cancelled, and any pass credit was returned.", "success")
    return redirect(url_for("web.my_bookings"))


@bp.route("/waitlist/<int:session_id>/leave", methods=["POST"])
@login_required
def leave_waitlist(session_id):
    try:
        service.leave_waitlist(g.conn, g.member["id"], session_id)
    except BookingError as error:
        flash(str(error), "error")
    else:
        flash("You left the waitlist.", "success")
    return redirect(url_for("web.my_bookings"))


@bp.route("/passes", methods=["POST"])
@login_required
def buy_pass():
    try:
        service.buy_pass(g.conn, g.member["id"], request.form.get("pass_type"))
    except BookingError as error:
        flash(str(error), "error")
    else:
        flash("Pass added to your account.", "success")
    return redirect(url_for("web.my_bookings"))