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

Decision: I test the service layers of both domains directly with pytest, using a fresh in-memory SQLite database per test. I also have a now parameter instead of a real clock in order to facilitate testing. Coverage is measured only on the scheduling and bookings packages (currently 97%). Routes get a small set of end-to-end tests through Flask's test clients. Templates and css are checked by hand.

Alternatives considered: Testing everything through HTTP routes, rejected because it is slower and mostly tests framework glue instead of rules. 

Consequences: The whole suite runs in a few seconds and protects every booking rule, including the Observer and Command behaviour. The cost is that template wording and page layout could break without a test noticing, and the rollback branches for unexpected database errors are untested.




5. One thing you deliberately chose not to build, and why. 

Date: 2026-10-02

Status: Decided

Context: When a waitlisted member is promoted, they only find out by checking their bookings page. Telling them proactively would need email or SMS.

Decision: I didn't build notifications. Promotions are recorded in the audit log and appear on the member's bookings page.

Alternatives considered: Sending an email on promotion. I rejected it because it needs an external mail service, which the deployment contract discourages and is overly-complicated to implement. An in-app notifications table was also rejected, because it adds a table and UI without teaching anything new about the architecture

Consequences: A promoted member only finds out by checking their bookings page, and the promotion shows up in the audit log, so the app is less convenient for them. 

6. The split

Date: 2026-11-16

Status: Decided

Context: Assignment 2 requires the monolith to become exactly two services, each in its own container with its own database, talking to each other only over HTTP.

Decision: I kept the seam exactly where ADR-2 put it. The Scheduling service owns class_types, instructors and sessions, and answers two requests: GET /sessions (upcoming sessions) and GET /sessions/{id} (one session with its class and instructor names, or 404). The Bookings service owns members and login, passes, bookings, the waitlist and the audit log. The only thing that crosses the seam is session information, and it only flows one way: Bookings asks Scheduling, and Scheduling never calls Bookings. Every call across the seam goes through one file, bookings/scheduling_client.py, which reads the Scheduling address from SCHEDULING_URL and gives up after SCHEDULING_TIMEOUT_S (2 seconds). The cross-seam flows are server side: booking a class (Bookings needs the session's capacity and status), listing a member's bookings and waitlist (they need class names and times), and the schedule with spots left.

ADR-2 held. In Assignment 1, Bookings already reached Scheduling only through Scheduling's service functions (six call sites), no SQL query joined across the two domains, and session_id was already a plain number. So the split meant replacing those six function calls with HTTP calls, not redesigning the data.

Alternatives considered: Moving capacity checks and the waitlist into Scheduling, so that Scheduling decides whether a class is full. Rejected because counting bookings needs the bookings table, so Scheduling would have to call Bookings, and the two services would depend on each other in both directions. 

Consequences: Scheduling works on its own, because it depends on nothing. Bookings depends on Scheduling: if Scheduling is down, anything that needs session details cannot work fully, so those calls must fail in a designed way (handled in a later step). Listing a member's bookings now costs one HTTP call per booking instead of one database query 

Update (2026-11-18): The UI is now static pages in ui/ that call both services from the browser. The schedule page gets the classes from Scheduling and the spots and my own status from Bookings and combines them, so it still shows the classes if Bookings is down. Booking stays on the server because the capacity check can't be skipped. Login now uses a signed token instead of a cookie, because the UI and the services are on different websites and browsers block cookies between sites.

7. Data and migrations

Date: 2026-11-18

Status: Decided

Context:
In Assignment 1 both domains shared one SQLite file (ADR-3) and the tables were created on every start with CREATE TABLE IF NOT EXISTS. Now each service needs its own SQL Server database, and I need to be able to change a table without losing the data already in it.

Decision:
There was no real data to move since Assignment 1 only had demo data, so each table moved to the database of the service that owns it. Scheduling has class_types, instructors and sessions, and Bookings has members, passes, bookings, waitlist_entries and audit_log. Each service logs in with its own user that only exists in its own database, so it can't read the other service's tables. Tables are now created and changed by numbered SQL files in each service's migrations folder. When a service starts, my migration runner applies any file that isn't recorded in the schema_migrations table yet, inside a transaction, so every migration runs exactly once. For example, 002 adds duration_minutes to sessions with DEFAULT 60, so the existing sessions get 60 and nothing is lost.

Because bookings.session_id now points to another database, it can't be a foreign key anymore, and one transaction can't cover both databases. To make up for this, Bookings asks Scheduling about the session before saving a booking and rejects sessions that don't exist or aren't open. When listing bookings, a session that can't be found is still shown, just without its details.

If a migration fails, its transaction is rolled back so the database doesn't change, the service doesn't start, and the health check fails the pipeline, so I fix the file and redeploy. If a migration works but is wrong, I write a new migration to fix it instead of editing the old one. If data is actually lost, I can restore the database from Azure SQL's automatic backups.

Alternatives considered:
Alembic, rejected because I don't use SQLAlchemy and my own runner is short enough to explain. Keeping CREATE TABLE IF NOT EXISTS, rejected because it can't change a table that already has data in it.

Consequences:
Each service can change its own tables without touching the other, but the database no longer stops a booking for a session that doesn't exist, so my code and tests have to. Running migrations at startup is only safe because each service runs as one container with one worker.


8. Serverless hosting on Azure

Date: 2026-11-27

Status: Decided

Context:
The system has to run in my Azure for Students subscription ($100 of credit, no card) and cost almost nothing when nobody uses it, so everything has to scale to zero.

Decision:
Each service runs as an Azure Container App on the Consumption plan with 0.25 vCPU, 0.5 GiB, minimum 0 and maximum 1 replica. Each has its own serverless Azure SQL database (0.5 to 1 vCore) on the free offer, which pauses after 60 minutes without use. The UI is a Storage static website, images are in GitHub Container Registry (free, so no Azure Container Registry), logs go to the Log Analytics workspace the Container Apps environment creates, and the pipeline signs in as a managed identity with OIDC, so no Azure password is stored. The cost model is pay-per-use: Container Apps only charge while a replica is running, a paused database charges nothing for compute, and the storage and logs cost cents. The SQL server is in [REGION] instead of switzerlandnorth like everything else, because switzerlandnorth and germanywestcentral weren't accepting new SQL servers.

Scale-to-zero has consequences. The first request after a quiet period has to start the container and may also find the database paused, which takes about a minute to resume. Meanwhile Azure answers 503 "App port is not ready", so the UI waits and retries with a "starting up" message. The services connect with retries and backoff (about 45 seconds at startup, a few seconds per request), gunicorn's timeout is 120 seconds so startup isn't killed while it waits, and Bookings waits 10 seconds for Scheduling on Azure instead of 2 because Scheduling may be asleep too. Migrations run at startup, which is only safe because there is at most one replica with one gunicorn worker, so they can never run twice at once. The deploy's health check waits up to 5 minutes for this.

At 100x traffic I would keep at least one replica running (no cold starts) and allow several, move migrations out of startup into a separate pipeline step so replicas can't race, move the databases off the free offer to more vCores, and add a batch endpoint in Scheduling so listing bookings doesn't make one call per booking.

Alternatives considered:
Always-on hosting (App Service or a VM), rejected because it charges even when idle and is out of scope. Bicep or Terraform instead of az commands, rejected because the setup is small and I can explain each command, but it would be worth it for a second environment.

Consequences:
Idle, the system costs close to nothing, but the first user after a quiet period waits up to about a minute. The single replica means no scaling under load and a few seconds of downtime during each deploy.




9. Pipeline and testing

Date: 2026-11-27

Status: Decided

Context:
Changes reach main only through pull requests, and every push to main deploys, so CI has to catch problems before they reach Azure.

Decision:
CI (ci.yml) runs on every branch push and pull request, and gates on: ruff lint, unit tests for each service against a real SQL Server container with at least 70% coverage of the core logic, building both Docker images, an integration test of the whole system in docker compose, and checking system.yaml and the OpenAPI documents against their schemas and against the code. CD (cd.yml) runs on main only: it runs the same CI first, then pushes the images tagged with the commit SHA, deploys them, and fails unless both /health endpoints report that SHA within 5 minutes. The test database password is generated for each run, so CI needs no secrets.

The cross-seam test works on two levels. In Bookings' unit tests, Scheduling is replaced by a stub (tests/scheduling_stub.py) that answers from a dictionary and can pretend to be down, because it keeps the tests fast and lets me test the "Scheduling is down" cases on purpose. The real HTTP client is tested separately with fake responses (timeout, connection refused, 404, 500). The integration test then runs both real services in compose and books a class over HTTP, and it runs again with Scheduling stopped to check that Bookings degrades instead of failing.

Deliberately not tested: the UI's JavaScript (I tested it by hand), behaviour that only exists on Azure (cold starts, encrypted connections), which the deploy's health check covers, two members booking the last spot at the same moment, and performance.

Alternatives considered:
Testing against SQLite, rejected because SQL Server's SQL is different and it would hide real bugs. A contract-testing tool like Pact, rejected as too much for two services, since the OpenAPI checks and the integration test already cover the contract.

Consequences:
A broken build, failing test or wrong system.yaml can't reach Azure. CI takes about 10 minutes because it starts SQL Server several times, and a bug only in the UI or only on Azure can still get through.
