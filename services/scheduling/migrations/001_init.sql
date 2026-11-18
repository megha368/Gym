-- 001: the Scheduling tables from Assignment 1, ported from SQLite to SQL Server.
-- Applied migrations are never edited: any change goes in a new numbered file.

CREATE TABLE class_types (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    name        NVARCHAR(100) NOT NULL UNIQUE,
    description NVARCHAR(500) NULL
);

CREATE TABLE instructors (
    id   INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL
);

-- start_time stays ISO text (2026-11-16T18:00:00), as in Assignment 1, so the code that
-- compares and formats it is unchanged. Text in this fixed format sorts in time order.
CREATE TABLE sessions (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    class_type_id INT NOT NULL REFERENCES class_types(id),
    instructor_id INT NOT NULL REFERENCES instructors(id),
    start_time    NVARCHAR(19) NOT NULL,
    capacity      INT NOT NULL CHECK (capacity > 0),
    status        NVARCHAR(20) NOT NULL DEFAULT 'scheduled'
                  CHECK (status IN ('scheduled', 'cancelled'))
);
