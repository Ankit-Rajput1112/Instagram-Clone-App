# create_messages_table.py
import sqlite3
DB = "instaclone.db"

sql = """
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sender_id INTEGER NOT NULL,
  receiver_id INTEGER NOT NULL,
  text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(sender_id) REFERENCES users(id),
  FOREIGN KEY(receiver_id) REFERENCES users(id)
);
"""

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute(sql)
conn.commit()
cur.close()
conn.close()
print("messages table created (if it did not already exist).")
