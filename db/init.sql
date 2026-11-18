-- Local development only: creates one database per service and one login per service.
--
-- Run by the one-off "db-init" service in docker-compose.yml, as the SQL Server admin (sa).
-- The passwords are NOT in this file: sqlcmd fills in $(SCHEDULING_DB_PASSWORD) and
-- $(BOOKINGS_DB_PASSWORD) from variables that compose reads from your .env file.
--
-- Idempotent: every step first checks whether the thing already exists, so running this
-- script again (every "docker compose up") changes nothing and loses no data.
--
-- On Azure this script is not used: the databases and logins are created once during the
-- initial setup (see README).

-- 1. One database per service
IF DB_ID('scheduling') IS NULL CREATE DATABASE scheduling;
IF DB_ID('bookings') IS NULL CREATE DATABASE bookings;
GO

-- 2. One login per service (a login = a username/password for the whole SQL Server)
IF SUSER_ID('scheduling_user') IS NULL
    CREATE LOGIN scheduling_user WITH PASSWORD = '$(SCHEDULING_DB_PASSWORD)';
IF SUSER_ID('bookings_user') IS NULL
    CREATE LOGIN bookings_user WITH PASSWORD = '$(BOOKINGS_DB_PASSWORD)';
GO

-- 3. Each login gets a user inside ITS OWN database only, as owner of that database
--    (owner, because its migrations create and change tables). Neither login has a user
--    in the other database, so scheduling_user cannot read bookings' tables, and vice versa.
USE scheduling;
IF USER_ID('scheduling_user') IS NULL
    CREATE USER scheduling_user FOR LOGIN scheduling_user;
ALTER ROLE db_owner ADD MEMBER scheduling_user;
GO

USE bookings;
IF USER_ID('bookings_user') IS NULL
    CREATE USER bookings_user FOR LOGIN bookings_user;
ALTER ROLE db_owner ADD MEMBER bookings_user;
GO

PRINT 'db/init.sql finished: databases and logins are ready.';
