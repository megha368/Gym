def add_member(conn, name, email, password_hash):
    cur = conn.execute(
        "INSERT INTO members (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    return cur.lastrowid


def get_member_by_email(conn, email):
    return conn.execute(
        "SELECT * FROM members WHERE email = ?", (email,)
    ).fetchone()


def get_member_by_id(conn, member_id):
    return conn.execute(
        "SELECT * FROM members WHERE id = ?", (member_id,)
    ).fetchone()