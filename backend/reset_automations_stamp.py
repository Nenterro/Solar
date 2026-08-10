import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "solar.db")
conn = sqlite3.connect(db_path)
c = conn.execute("UPDATE automations SET last_triggered = NULL").rowcount
conn.commit()
conn.close()

print(f"Reset {c} automation records (set last_triggered = NULL) so they trigger fresh today.")
