import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "solar.db")
conn = sqlite3.connect(db_path)

c1 = conn.execute("UPDATE telemetry_history SET battery_pct = 100.0 WHERE battery_pct > 100.0").rowcount
c2 = conn.execute("UPDATE telemetry_history SET battery_pct = 0.0 WHERE battery_pct < 0.0").rowcount
c3 = conn.execute("UPDATE telemetry_history SET battery_v = 54.0 WHERE battery_v > 70.0 OR battery_v < 35.0").rowcount
conn.commit()
conn.close()

print(f"Purged {c1} SOC > 100% rows, {c2} negative SOC rows, and {c3} corrupted battery voltage rows from SQLite DB.")
