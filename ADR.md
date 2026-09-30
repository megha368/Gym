1. Backend language/framework choice

Date: 2026-09-30

Status: Decided

Context:
The application needs to support two backend feature domains, SQLite persistence, authentication, testing, and several design patterns while remaining a small single-process application. The technology should also be simple enough that the entire implementation can be understood and explained during the written comprehension check.

Decision: 
I chose Python with Flask as the backend framework. I chose Python because we are already using it in class exercises, so it serves as good practice and is consistent with the language used in the course. I chose Flask because it provides routing and request handling without the additional complexity of a larger framework like Django or FastApi, making it appropriate for this relatively small application. I also chose to incorporate login because in order to book a class and see your classes booked, you need an account. 

Alternatives considered: 
I considered Django, but rejected it because the application does not require its larger set of built-in features and would introduce unnecessary framework complexity. I also considered FastAPI, but Flask provides a simpler setup for our template-based web application. Flask does everything I need and is easier to learn as compared to the other two alternatives. I also considered adding authentication functionality, but rejected it because the core application can demonstrate its booking and scheduling workflows without authentication. Adding authentication would increase complexity without providing significant value to the assignment's required architecture.

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
I considered using separate databases for each domain, but rejected this because the assignment requires SQLite at one documented path and because the application does not need the complexity of multiple databases.

Consequences: 
Everything is in one database, making things easier to pinpoint and access. 