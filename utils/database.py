import sqlite3

conn = sqlite3.connect("data/database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    channel_id INTEGER,
    claimed_by INTEGER,
    status TEXT
)
""")

conn.commit()

def create_ticket(user_id, channel_id):
    cursor.execute(
        "INSERT INTO tickets (user_id, channel_id, claimed_by, status) VALUES (?, ?, ?, ?)",
        (user_id, channel_id, None, "OPEN")
    )
    conn.commit()
    return cursor.lastrowid

def claim_ticket(channel_id, staff_id):
    cursor.execute(
        "UPDATE tickets SET claimed_by=? WHERE channel_id=?",
        (staff_id, channel_id)
    )
    conn.commit()

def close_ticket(channel_id):
    cursor.execute(
        "UPDATE tickets SET status='CLOSED' WHERE channel_id=?",
        (channel_id,)
    )
    conn.commit()
cursor.execute("""
CREATE TABLE IF NOT EXISTS tier_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tester_id INTEGER,
    candidate_id INTEGER,
    region TEXT,
    gamemode TEXT,
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

def save_tier_result(tester_id, candidate_id, region, gamemode, result):
    cursor.execute(
        "INSERT INTO tier_results (tester_id, candidate_id, region, gamemode, result) VALUES (?, ?, ?, ?, ?)",
        (tester_id, candidate_id, region, gamemode, result)
    )
    conn.commit()
cursor.execute("""
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    experience TEXT,
    availability TEXT,
    reason TEXT,
    status TEXT DEFAULT 'PENDING',
    reviewed_by INTEGER
)
""")

conn.commit()

def create_application(user_id, experience, availability, reason):
    cursor.execute(
        "INSERT INTO applications (user_id, experience, availability, reason) VALUES (?, ?, ?, ?)",
        (user_id, experience, availability, reason)
    )
    conn.commit()
    return cursor.lastrowid

def update_application_status(app_id, status, staff_id):
    cursor.execute(
        "UPDATE applications SET status=?, reviewed_by=? WHERE id=?",
        (status, staff_id, app_id)
    )
    conn.commit()

def has_application(user_id):
    cursor.execute(
        "SELECT * FROM applications WHERE user_id=? AND status='PENDING'",
        (user_id,)
    )
def get_tier_stats():
    cursor.execute("SELECT gamemode, COUNT(*) FROM tier_results GROUP BY gamemode")
    return cursor.fetchall()