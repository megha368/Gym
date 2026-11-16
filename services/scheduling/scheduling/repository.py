# Add a brand new fitness class (e.g. Yoga, Pilates, Boxing) to the class_types table in the database 
def add_class_type(conn, name, description=None): # default to no description 
    # send command to db 
    cur = conn.execute("INSERT INTO class_types (name, description) OUTPUT INSERTED.id VALUES (%s, %s)", (name, description)) # avoiding SQL injection
    new_id = cur.fetchone()["id"] # the id SQL Server gave the new row (OUTPUT INSERTED.id)
    conn.commit() # save the changes
    return new_id


# Add a brand new instructor to the instructors table in the database 
def add_instructor(conn, name):
    cur = conn.execute("INSERT INTO instructors (name) OUTPUT INSERTED.id VALUES (%s)", (name,))
    new_id = cur.fetchone()["id"] # the id SQL Server gave the new row (OUTPUT INSERTED.id)
    conn.commit() # save the changes
    return new_id

# Add a brand new session to the sessions table in the database 
def add_session(conn, class_type_id, instructor_id, start_time, capacity):
    cur = conn.execute("INSERT INTO sessions (class_type_id, instructor_id, start_time, capacity) OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)", (class_type_id, instructor_id, start_time, capacity))
    new_id = cur.fetchone()["id"] # the id SQL Server gave the new row (OUTPUT INSERTED.id)
    conn.commit() # save the changes
    return new_id

# Get information about a given class type 
def get_class_type(conn, class_type_id):
    return conn.execute("SELECT * FROM class_types WHERE id = %s", (class_type_id,)).fetchone() # if item doesn't exist, fetchone() will return None

# Get information about a given instructor 
def get_instructor(conn, instructor_id):
    return conn.execute(
        "SELECT * FROM instructors WHERE id = %s", (instructor_id,)
    ).fetchone()

# Get information about a given session 
def get_session(conn, session_id):
    return conn.execute(
        "SELECT * FROM sessions WHERE id = %s", (session_id,)
    ).fetchone()


# Session status is set to "scheduled" by default when you add a session. This allows you to change the status 
def set_session_status(conn, session_id, status):
    conn.execute("UPDATE sessions SET status = %s WHERE id = %s", (status, session_id))
    conn.commit() 

# Reuturns a list of upcoming sessions from a certain point onward 
def list_scheduled_sessions_from(conn, from_time):
    """Scheduled sessions starting at or after from_time, soonest first."""
    return conn.execute(
        """
        SELECT s.id, ct.name AS class_name, i.name AS instructor_name,
               s.start_time, s.capacity, s.status
        FROM sessions s
        JOIN class_types ct ON ct.id = s.class_type_id
        JOIN instructors i  ON i.id  = s.instructor_id
        WHERE s.status = 'scheduled' AND s.start_time >= %s
        ORDER BY s.start_time
        """,
        (from_time,),
    ).fetchall()

def get_session_with_names(conn, session_id):
    return conn.execute(
        """
        SELECT s.id, ct.name AS class_name, i.name AS instructor_name,
               s.start_time, s.capacity, s.status
        FROM sessions s
        JOIN class_types ct ON ct.id = s.class_type_id
        JOIN instructors i  ON i.id  = s.instructor_id
        WHERE s.id = %s
        """,
        (session_id,),
    ).fetchone()