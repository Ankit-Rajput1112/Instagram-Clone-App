import sqlite3
DB = "instaclone.db"
sql = """
CREATE TABLE IF NOT EXISTS message_comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(message_id) REFERENCES messages(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
);
"""
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute(sql)
conn.commit()
cur.close()
conn.close()
print("message_comments table created (if not existed).")
