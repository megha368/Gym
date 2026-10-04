1. Backend language/framework choice

Date: 2026-09-30

Status: Decided

Context:
The application needs to support two backend feature domains, SQLite persistence, authentication, testing, and several design patterns while remaining a small single-process application. The technology should also be simple enough that the entire implementation can be understood and explained during the written comprehension check.

Decision: 
I chose Python with Flask as the backend framework. I chose Python because we are already using it in class exercises, so it serves as good practice and is consistent with the language used in the course. I chose Flask because it provides routing and request handling without the additional complexity of a larger framework like Django or FastApi, making it appropriate for this relatively small application. I also chose to incorporate login because in order to book a class and see your classes booked, you need an account. 

Alternatives considered: 
I considered Django, but rejected it because the application does not require its larger set of built-in features and would introduce unnecessary framework complexity. I also considered FastAPI, but Flask provides a simpler setup for our template-based web application. Flask does everything I need and is easier to learn as compared to the other two alternatives. I also considered no login at all: rejected because bookings must belong to a specific member. 

Consequences: 
This keeps the application lightweight and easier to understand, while still providing everything required for the backend. I will also use Jinja templates with HTML/CSS for the frontend, SQLite (which allows me to store an entire database inside a single local file on my computer), Pytohn's built-in sqlite3, and pytest/pytest-cov for testing (because I've used it before). This will keep the dependency count within the assignment's 12-package guideline. 




2. How you scoped your two feature domains to be independently modularizable 

Date: 2026-09-30

Status: Decided

Context: 
The application requires two distinct backend feature domains that should have separate responsibilities and be capable of becoming independent services in the future. The domains are "Class Scheduling" and "Members & Bookings", which need to interact when a member books or cancels a class.

Decision: 
I will separate the application into a Class Scheduling domain responsible for class types, instructors, sessions, and capacity, and a Members & Bookings domain responsible for members, passes, bookings, and waitlists. The domains will use separate code modules and services while sharing one SQLite database. Bookings will store only a session_id rather than duplicating session information. 

Alternatives considered: 
I considered using separate databases for each domain, but rejected this because the assignment requires SQLite at one documented path and because the application does not need the complexity of multiple databases. A single shared module was rejected because it would allow booking code to directly query session tables instead of requiring an explicit module import, preventing the domains from ever being split.

Consequences: 
Everything is in one database, making things easier to pinpoint and access. Each domain could later become its own service, but Bookings cannot join against session data in SQL, so it calls Scheduling's service file whenever it needs session details, for example when listing a member's bookings.




3. Data model: how Bookings relates to Scheduling in SQLite

Date: 2026-10-01

Status: Decided

Context: Bookings must refer to the sessions they reserve, but the 'Scheduling' and 'Members & Bookings' domains need to stay independently separable in case Scheduling later becomes its own service with its own database. Both domains store their tables in one SQLite file.

Decision: Scheduling owns class_types, instructors and sessions; Bookings owns members, passes, bookings, waitlist_entries and audit_log. bookings.session_id and waitlist_entries.session_id are plain integers with no foreign key, and the booking service validates them by calling Scheduling's service.

Alternatives considered: A real foreign key from bookings.session_id to sessions.id was rejected because the database would then link the two domains' tables, and that constraint would have to be dropped if Scheduling later became its own service. Also, separate SQLite files per domain, rejected because the assignment requires one documented database path and it would add complexity without benefit.

Consequences: The database can no longer reject a booking for a nonexistent session, so the booking service must check it and tests must cover that. In exchange, Scheduling could later be moved out without changing any Bookings table. 




4. Your testing approach

Date: 2026-10-04

Status: Decided

Context: The assignment requires at least 70% coverage of core business logic, not framework glue. My rules (capacity, passes, waitlist promotion) depend on SQLite constraints and on the current time.

Decision: I test the service layers of both domains directly with pytest, using a fresh in-memory SQLite database per test (get_connection(":memory:") makes a throwaway database in RAM that vanishes after the test, so tests can't affect each other) and a `now` parameter instead of the real clock, and I measure coverage only on the `scheduling` and `bookings` packages (currently 97%). Routes get a small set of end-to-end tests (tests the entire system) through Flask's test client, and templates and CSS are only checked by hand.

Alternatives considered: Testing everything through HTTP routes, rejected because it is slower and mostly tests framework glue instead of rules. 

Consequences: The whole suite runs in a few seconds and protects every booking rule, including the Observer and Command behaviour. The cost is that template wording and page layout could break without a test noticing, and the rollback branches for unexpected database errors are untested.




5. One thing you deliberately chose not to build, and why. 

Date: 2026-10-02

Status: Decided

Context: When a waitlisted member is promoted, they only find out by checking their bookings page. Telling them proactively would need email or SMS.

Decision: I didn't build notifications. Promotions are recorded in the audit log and appear on the member's bookings page.

Alternatives considered: Sending an email on promotion. I rejected it because it needs an external mail service, which the deployment contract discourages and is overly-complicated to implement. An in-app notifications table was also rejected, because it adds a table and UI without teaching anything new about the architecture

Consequences: A promoted member only finds out by checking their bookings page, and the promotion shows up in the audit log, so the app is less convenient for them. 
