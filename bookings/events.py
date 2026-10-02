from dataclasses import dataclass


@dataclass(frozen=True)
class BookingCancelled:
    """Announcement: a confirmed booking was cancelled and its spot is free."""
    booking_id: int
    member_id: int
    session_id: int


class EventBus:
    """Keeps a list of handlers per event type and calls them when an event is published."""

    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_type, handler):
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event, conn, now):
        for handler in self._subscribers.get(type(event), []):
            handler(event, conn, now)


# The bus the app uses. Tests can pass their own EventBus() instead.
default_bus = EventBus()