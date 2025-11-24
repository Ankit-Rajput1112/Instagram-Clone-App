# analytics.py - generate simple plots from the sqlite DB
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime

DB = 'instaclone.db'

def likes_per_day():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT date(created_at), COUNT(*) FROM likes GROUP BY date(created_at) ORDER BY date(created_at)" )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print('No likes data found.')
        return
    dates = [datetime.strptime(r[0], '%Y-%m-%d').date() for r in rows]
    counts = [r[1] for r in rows]
    plt.figure(figsize=(8,4))
    plt.plot(dates, counts)
    plt.xlabel('Date')
    plt.ylabel('Likes')
    plt.title('Likes per Day')
    plt.tight_layout()
    plt.savefig('likes_per_day.png')
    print('Saved likes_per_day.png')

if __name__ == '__main__':
    likes_per_day()
