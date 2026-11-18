def add_member(conn, name, email, password_hash):
    cur = conn.execute(
        "INSERT INTO members (name, email, password_hash) OUTPUT INSERTED.id VALUES (%s, %s, %s)",
        (name, email, password_hash),
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    return new_id


def get_member_by_email(conn, email):
    return conn.execute(
        "SELECT * FROM members WHERE email = %s", (email,)
    ).fetchone()


def get_member_by_id(conn, member_id):
    return conn.execute(
        "SELECT * FROM members WHERE id = %s", (member_id,)
    ).fetchone()


def add_pass(conn, member_id, pass_type, remaining_uses, expires_at):
    cur = conn.execute(
        "INSERT INTO passes (member_id, type, remaining_uses, expires_at) OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)",
        (member_id, pass_type, remaining_uses, expires_at),
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    return new_id


def get_pass(conn, pass_id):
    return conn.execute("SELECT * FROM passes WHERE id = %s", (pass_id,)).fetchone()


def list_passes_for_member(conn, member_id):
    return conn.execute(
        "SELECT * FROM passes WHERE member_id = %s", (member_id,)
    ).fetchall()


def set_pass_remaining(conn, pass_id, remaining_uses):
    """Does not commit: the caller commits together with the booking."""
    conn.execute(
        "UPDATE passes SET remaining_uses = %s WHERE id = %s", (remaining_uses, pass_id)
    )


def add_booking(conn, member_id, session_id, pass_id):
    """Does not commit: the caller commits together with the pass update."""
    cur = conn.execute(
        "INSERT INTO bookings (member_id, session_id, pass_id) OUTPUT INSERTED.id VALUES (%s, %s, %s)",
        (member_id, session_id, pass_id),
    )
    return cur.fetchone()["id"]


def get_confirmed_booking(conn, member_id, session_id):
    return conn.execute(
        "SELECT * FROM bookings "
        "WHERE member_id = %s AND session_id = %s AND status = 'confirmed'",
        (member_id, session_id),
    ).fetchone()


def count_confirmed_bookings(conn, session_id):
    return conn.execute(
        "SELECT COUNT(*) AS n FROM bookings WHERE session_id = %s AND status = 'confirmed'",
        (session_id,),
    ).fetchone()["n"]


def list_confirmed_bookings_for_member(conn, member_id):
    return conn.execute(
        "SELECT * FROM bookings WHERE member_id = %s AND status = 'confirmed' "
        "ORDER BY created_at",
        (member_id,),
    ).fetchall()

def add_waitlist_entry(conn, member_id, session_id):
    """Does not commit: the service commits."""
    cur = conn.execute(
        "INSERT INTO waitlist_entries (member_id, session_id) OUTPUT INSERTED.id VALUES (%s, %s)",
        (member_id, session_id),
    )
    return cur.fetchone()["id"]


def get_waitlist_entry(conn, member_id, session_id):
    return conn.execute(
        "SELECT * FROM waitlist_entries WHERE member_id = %s AND session_id = %s",
        (member_id, session_id),
    ).fetchone()


def remove_waitlist_entry(conn, entry_id):
    """Does not commit: the service commits."""
    conn.execute("DELETE FROM waitlist_entries WHERE id = %s", (entry_id,))


def count_waitlist_up_to(conn, session_id, entry_id):
    """How many entries for this session are at or before entry_id (= position) (what's the user's position on the waitlist)."""
    return conn.execute(
        "SELECT COUNT(*) AS n FROM waitlist_entries WHERE session_id = %s AND id <= %s",
        (session_id, entry_id),
    ).fetchone()["n"]


def get_booking(conn, booking_id):
    return conn.execute(
        "SELECT * FROM bookings WHERE id = %s", (booking_id,)
    ).fetchone()


def set_booking_status(conn, booking_id, status):
    """Does not commit: the service commits together with the pass refund."""
    conn.execute("UPDATE bookings SET status = %s WHERE id = %s", (status, booking_id))


def get_first_waitlist_entry(conn, session_id):
    """The member who has been waiting longest for this session, or None."""
    return conn.execute(
        "SELECT TOP 1 * FROM waitlist_entries WHERE session_id = %s ORDER BY id",
        (session_id,),
    ).fetchone()


def add_audit_entry(conn, member_id, action, session_id, details=None):
    """Does not commit: run_command commits after writing all entries."""
    conn.execute(
        "INSERT INTO audit_log (member_id, action, session_id, details) "
        "VALUES (%s, %s, %s, %s)",
        (member_id, action, session_id, details),
    )


def list_audit_entries(conn, member_id=None):
    if member_id is None:
        return conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    return conn.execute(
        "SELECT * FROM audit_log WHERE member_id = %s ORDER BY id", (member_id,)
    ).fetchall()


def list_waitlist_entries_for_member(conn, member_id):
    return conn.execute(
        "SELECT * FROM waitlist_entries WHERE member_id = %s ORDER BY id",
        (member_id,),
    ).fetchall()