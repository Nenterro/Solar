import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "solar.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT timestamp, inverter_id, battery_pct, battery_v FROM telemetry_history WHERE battery_pct > 100 ORDER BY timestamp DESC LIMIT 30").fetchall()

print(f"Found {len(rows)} SOC spikes > 100% in telemetry_history:")
for r in rows:
    print(f"  {r['timestamp']} | {r['inverter_id']} | SOC: {r['battery_pct']}% | Voltage: {r['battery_v']}V")

# Check max SOC recorded
max_row = conn.execute("SELECT timestamp, inverter_id, battery_pct, battery_v FROM telemetry_history ORDER BY battery_pct DESC LIMIT 5").fetchall()
print("\nTop 5 Max SOC values recorded:")
for r in max_row:
    print(f"  {r['timestamp']} | {r['inverter_id']} | SOC: {r['battery_pct']}% | Voltage: {r['battery_v']}V")
