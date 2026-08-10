import sqlite3, os, json

db_path = os.path.join(os.path.dirname(__file__), "solar.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT * FROM automations").fetchall()

print(f"=========================================================================")
print(f"FOUND {len(rows)} AUTOMATION RECORDS IN SQLITE DB:")
print(f"=========================================================================")

for r in rows:
    print(f"ID: {r['id']}")
    print(f"  Name: {r['name']}")
    print(f"  Time of Day: {repr(r['time_of_day'])}")
    print(f"  Inverter ID: {r['inverter_id']}")
    print(f"  Enabled: {r['enabled']}")
    print(f"  Actions: {r['actions']}")
    print(f"  Last Triggered: {r['last_triggered']}")
    print("-" * 50)

conn.close()
