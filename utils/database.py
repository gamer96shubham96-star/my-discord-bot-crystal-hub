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
