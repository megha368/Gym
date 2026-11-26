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

-- 3. Each login gets a user inside ITS OWN database only. Neither login has a user in the
--    other database, so scheduling_user cannot read bookings' tables, and vice versa.
--    Its roles let it read and write data and run migrations (create and change tables),
--    and nothing more: the same three roles as on Azure.
USE scheduling;
IF USER_ID('scheduling_user') IS NULL
    CREATE USER scheduling_user FOR LOGIN scheduling_user;
ALTER ROLE db_ddladmin ADD MEMBER scheduling_user;
ALTER ROLE db_datareader ADD MEMBER scheduling_user;
ALTER ROLE db_datawriter ADD MEMBER scheduling_user;
IF IS_ROLEMEMBER('db_owner', 'scheduling_user') = 1
    ALTER ROLE db_owner DROP MEMBER scheduling_user;  -- older versions of this script used db_owner
GO

USE bookings;
IF USER_ID('bookings_user') IS NULL
    CREATE USER bookings_user FOR LOGIN bookings_user;
ALTER ROLE db_ddladmin ADD MEMBER bookings_user;
ALTER ROLE db_datareader ADD MEMBER bookings_user;
ALTER ROLE db_datawriter ADD MEMBER bookings_user;
IF IS_ROLEMEMBER('db_owner', 'bookings_user') = 1
    ALTER ROLE db_owner DROP MEMBER bookings_user;
GO

PRINT 'db/init.sql finished: databases and logins are ready.';
