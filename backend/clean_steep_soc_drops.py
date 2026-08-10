import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "solar.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

inverter_ids = ['inv1', 'inv2', 'inv3', 'all']
total_cleaned = 0

print("=========================================================================")
print("CLEANING SINGLE-MINUTE STEEP SOC DROPS IN TELEMETRY_HISTORY")
print("=========================================================================")

for inv in inverter_ids:
    rows = conn.execute("""
        SELECT id, timestamp, battery_pct
        FROM telemetry_history
        WHERE inverter_id = ?
        ORDER BY timestamp ASC
    """, (inv,)).fetchall()

    cleaned_for_inv = 0
    for i in range(1, len(rows) - 1):
        row_prev = rows[i - 1]
        row_curr = rows[i]
        row_next = rows[i + 1]

        soc_prev = row_prev["battery_pct"]
        soc_curr = row_curr["battery_pct"]
        soc_next = row_next["battery_pct"]

        # Check if current minute dropped > 4% below previous and next minute jumped back up within 2% of previous
        if soc_curr < (soc_prev - 4.0) and soc_next >= (soc_prev - 2.0):
            smoothed_soc = round((soc_prev + soc_next) / 2.0, 1)
            conn.execute("UPDATE telemetry_history SET battery_pct = ? WHERE id = ?", (smoothed_soc, row_curr["id"]))
            cleaned_for_inv += 1

    total_cleaned += cleaned_for_inv
    print(f"  [{inv:4s}] Smoothed {cleaned_for_inv} transient SOC dip points.")

conn.commit()
conn.close()

print(f"\nSUCCESS: Cleaned and smoothed {total_cleaned} single-minute SOC drop anomalies in SQLite DB.")
