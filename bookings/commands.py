from datetime import datetime

from bookings import repository, service


class BookCommand:
    """'Member wants a spot in this session' (books, or joins the waitlist if full)."""

    def __init__(self, member_id, session_id):
        self.member_id = member_id
        self.session_id = session_id

    def execute(self, conn, now, bus):
        return service.book_or_join_waitlist(
            conn, self.member_id, self.session_id, now=now
        )

    def audit_entries(self, result):
        if result["status"] == "confirmed":
            return [(self.member_id, "book", self.session_id,
                     f"booking_id={result['booking_id']}")]
        return [(self.member_id, "waitlist_join", self.session_id,
                 f"position={result['position']}")]


class CancelCommand:
    """'Member cancels this booking'. May also promote someone from the waitlist."""

    def __init__(self, member_id, booking_id):
        self.member_id = member_id
        self.booking_id = booking_id

    def execute(self, conn, now, bus):
        return service.cancel_booking(
            conn, self.member_id, self.booking_id, now=now, bus=bus
        )

    def audit_entries(self, result):
        entries = [(self.member_id, "cancel", result["session_id"],
                    f"booking_id={result['booking_id']}")]
        promoted = result["promoted"]
        if promoted:
            entries.append((
                promoted["member_id"], "promote", promoted["session_id"],
                f"booking_id={promoted['booking_id']}, "
                f"after cancellation of booking_id={result['booking_id']}",
            ))
        return entries


def run_command(conn, command, now=None, bus=None):
    """Execute a command, then record what happened in the audit log."""
    now = now or datetime.now()
    result = command.execute(conn, now, bus)
    for member_id, action, session_id, details in command.audit_entries(result):
        repository.add_audit_entry(conn, member_id, action, session_id, details)
    conn.commit()
    return result