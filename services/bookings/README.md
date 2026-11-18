# Bookings service

Owns members, login, passes, bookings, the waitlist and the audit log.
Database: its own SQL Server database (bookings-db).
Calls the scheduling service over HTTP (SCHEDULING_URL) for session details.
