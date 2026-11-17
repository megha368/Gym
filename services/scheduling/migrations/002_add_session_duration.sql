-- 002: every session gets a length in minutes.
--
-- The sessions table already holds data. Adding a NOT NULL column together with a DEFAULT
-- makes SQL Server fill in 60 for every existing row as part of this one statement, so no
-- session is lost and none is left without a value. New sessions also get 60 unless the
-- insert says otherwise.
ALTER TABLE sessions
    ADD duration_minutes INT NOT NULL
        CONSTRAINT df_sessions_duration_minutes DEFAULT 60
        CONSTRAINT ck_sessions_duration_minutes CHECK (duration_minutes > 0);
