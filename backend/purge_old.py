import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "solar.db")
TODAY_STR = "2026-08-09"

def purge_old_data():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"--- PRE-PURGE STATUS ---")
    d_before = cursor.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily_totals").fetchone()
    print(f"daily_totals before: {d_before[0]} rows (Min: {d_before[1]}, Max: {d_before[2]})")

    t_before = cursor.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM telemetry_history").fetchone()
    print(f"telemetry_history before: {t_before[0]} rows (Min: {t_before[1]}, Max: {t_before[2]})")

    # Purge telemetry_history before TODAY_STR (2026-08-09)
    cursor.execute("DELETE FROM telemetry_history WHERE timestamp < ?", (f"{TODAY_STR} 00:00:00",))
    t_deleted = cursor.rowcount

    # Purge daily_totals before TODAY_STR (2026-08-09)
    cursor.execute("DELETE FROM daily_totals WHERE date < ?", (TODAY_STR,))
    d_deleted = cursor.rowcount

    conn.commit()

    print(f"\n--- PURGE COMPLETE ---")
    print(f"Deleted {t_deleted} telemetry_history rows before {TODAY_STR}")
    print(f"Deleted {d_deleted} daily_totals rows before {TODAY_STR}")

    d_after = cursor.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM daily_totals").fetchone()
    print(f"daily_totals after: {d_after[0]} rows (Min: {d_after[1]}, Max: {d_after[2]})")

    t_after = cursor.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM telemetry_history").fetchone()
    print(f"telemetry_history after: {t_after[0]} rows (Min: {t_after[1]}, Max: {t_after[2]})")

    conn.close()

if __name__ == "__main__":
    purge_old_data()
