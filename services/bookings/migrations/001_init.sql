-- 001: the Members & Bookings tables from Assignment 1, ported from SQLite to SQL Server.
-- Applied migrations are never edited: any change goes in a new numbered file.

CREATE TABLE members (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    name          NVARCHAR(100) NOT NULL,
    email         NVARCHAR(255) NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    created_at    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

-- expires_at stays ISO text, as in Assignment 1 (compared as text in strategies.py)
CREATE TABLE passes (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    member_id      INT NOT NULL REFERENCES members(id),
    type           NVARCHAR(20) NOT NULL
                   CHECK (type IN ('drop_in', 'class_pack', 'membership')),
    remaining_uses INT NULL CHECK (remaining_uses IS NULL OR remaining_uses >= 0),
    expires_at     NVARCHAR(19) NULL,
    created_at     DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

-- session_id points at a session in the OTHER service's database, so it cannot be a
-- foreign key: it is a plain number, checked in code by asking Scheduling (ADR-3, ADR-7).
CREATE TABLE bookings (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    member_id  INT NOT NULL REFERENCES members(id),
    session_id INT NOT NULL,
    pass_id    INT NOT NULL REFERENCES passes(id),
    status     NVARCHAR(20) NOT NULL DEFAULT 'confirmed'
               CHECK (status IN ('confirmed', 'cancelled')),
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

-- A member can have only one CONFIRMED booking per session (cancelled ones don't count)
CREATE UNIQUE INDEX one_confirmed_booking_per_session
    ON bookings (member_id, session_id) WHERE status = 'confirmed';

CREATE TABLE waitlist_entries (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    member_id  INT NOT NULL REFERENCES members(id),
    session_id INT NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT one_waitlist_entry_per_session UNIQUE (member_id, session_id)
);

CREATE TABLE audit_log (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    member_id  INT NOT NULL REFERENCES members(id),
    action     NVARCHAR(50) NOT NULL,
    session_id INT NOT NULL,
    details    NVARCHAR(1000) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
