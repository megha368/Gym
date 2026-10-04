# Flow Studio: Gym Class Booking

A small web app for a gym/yoga studio (about 300 members and 40 sessions a week).
Members register, buy a pass, browse the weekly schedule, book classes, join a waitlist
when a class is full, and cancel for free. When someone cancels, the first person on the
waitlist is promoted automatically.

Built with Python, Flask, SQLite (built-in `sqlite3`), Jinja templates, and pytest.

## Setup

Requires Python 3.10 or newer (developed on 3.13).

```
git clone <your-repo-url>
cd <repo-folder>
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000. On first start the app creates the database and fills it with
a week of demo classes, so no manual setup is needed.

**On macOS**, port 5000 is often used by AirPlay Receiver. Use another port:
`PORT=5001 python app.py` (Windows PowerShell: `$env:PORT=5001; python app.py`).

To reset the data, stop the app and delete `data/gym.db`.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `5000` | Port the app listens on (it binds to `0.0.0.0`) |
| `DATA_DIR` | `data` | Folder for the SQLite file, which is `DATA_DIR/gym.db` |
| `SECRET_KEY` | `dev-only-change-me` | Signs the login cookie. Set a real value outside local development |
| `SEED_DEMO_DATA` | `1` | Set to `0` to skip creating demo classes on an empty database |

## Using the app

1. Click **Join** and create an account.
2. Open **My bookings** and add a pass (drop-in, class pack, or membership).
3. Go to **Schedule** and click **Book**. If a class is full, the button becomes
   **Join waitlist**.
4. Cancel from **My bookings**. Cancelling is free until the class starts and returns the
   pass credit, and the next waitlisted member with a valid pass gets the spot.

## Tests and coverage

```
python -m pytest
python -m pytest --cov=scheduling --cov=bookings --cov-report=term-missing
```

Latest result: 102 tests passing, 97% coverage of the `scheduling` and `bookings`
packages (the core business logic; target is at least 70%).

## Project structure

```
app.py                 entry point (python app.py)
config/                environment-based settings
database/              SQLite connection, table creation, demo data
scheduling/            Domain 1: class types, instructors, sessions, capacity
bookings/              Domain 2: members/login, passes, bookings, waitlist, audit log
  strategies.py        Strategy pattern: how each pass type is validated and used
  events.py            Observer pattern: in-process event bus
  commands.py          Command pattern: book/cancel commands that write the audit log
web/                   Flask routes, templates and CSS
tests/                 pytest suite
ADR.md                 architecture decision records
AI_USAGE.md            log of AI use
```

The two domains share one SQLite file but not each other's tables. Bookings stores only a
`session_id` and asks Scheduling's service for session details (see ADR-2 and ADR-3).

## Deployment contract (Assignment 2)

- Single process, started with `python app.py`, binding to `0.0.0.0`
- Port from `PORT`, SQLite path from `DATA_DIR` (`DATA_DIR/gym.db`)
- No interactive setup: tables and demo data are created on startup
- Everything is configured through environment variables; no `.env` file is needed
- One dependency manifest at the root: `requirements.txt`
- No Dockerfile, docker-compose file, or CI workflow

## Known limitations

- There is no admin screen: sessions come from the demo data (or from calling the
  scheduling service directly).
- No password reset, email verification, or notifications (see ADR-5).
- Uses Flask's development server, which is fine for this assignment.