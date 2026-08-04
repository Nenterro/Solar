import sys
import os
import sqlite3
from datetime import datetime

# Add current dir to sys.path
sys.path.insert(0, os.path.dirname(__file__))

import db
from dess_scraper import dess_scraper

def backfill_today():
    today_str = datetime.now(db.PKT).strftime("%Y-%m-%d")
    print(f"Backfilling today ({today_str}) intraday telemetry from DESSMonitor...")

    if not dess_scraper.token:
        if not dess_scraper.login():
            print("Failed to log in to DESSMonitor")
            return

    for inv_id in ["all", "inv1", "inv2", "inv3"]:
        recs = dess_scraper.fetch_cumulative_intraday_for_day(today_str, inv_id)
        print(f"Fetched {len(recs)} records for {inv_id}")

        if not recs:
            continue

        conn = db.get_db_connection()
        try:
            prev_solar, prev_load, prev_g_imp, prev_g_exp, prev_b_chg, prev_b_dis = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

            for i, r in enumerate(recs):
                ts_str = f"{today_str} {r['time']}:00"
                s_kwh = r["solar"]
                l_kwh = r["load"]
                gi_kwh = r["gridImport"]
                ge_kwh = r["gridExport"]
                bc_kwh = r["batteryCharge"]
                bd_kwh = r["batteryDischarge"]

                if i == 0:
                    delta_s = s_kwh
                    delta_l = l_kwh
                    delta_gi = gi_kwh
                    delta_ge = ge_kwh
                    delta_bc = bc_kwh
                    delta_bd = bd_kwh
                else:
                    delta_s = max(0.0, s_kwh - prev_solar)
                    delta_l = max(0.0, l_kwh - prev_load)
                    delta_gi = max(0.0, gi_kwh - prev_g_imp)
                    delta_ge = max(0.0, ge_kwh - prev_g_exp)
                    delta_bc = max(0.0, bc_kwh - prev_b_chg)
                    delta_bd = max(0.0, bd_kwh - prev_b_dis)

                prev_solar, prev_load, prev_g_imp, prev_g_exp, prev_b_chg, prev_b_dis = s_kwh, l_kwh, gi_kwh, ge_kwh, bc_kwh, bd_kwh

                # Convert 10-min delta kWh to Watts (kW = delta_kwh * 6)
                solar_w = delta_s * 6.0 * 1000.0
                load_w = delta_l * 6.0 * 1000.0
                grid_w = (delta_gi - delta_ge) * 6.0 * 1000.0
                bat_w = (delta_bc - delta_bd) * 6.0 * 1000.0
                bat_pct = r.get("batteryLevel", 80.0)

                # Upsert into telemetry_history
                conn.execute("""
                    INSERT INTO telemetry_history
                    (timestamp, inverter_id, solar_w, load_w, grid_w, battery_w, battery_pct, battery_v, grid_v, temp_c)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 53.3, 230.0, 45.0)
                """, (ts_str, inv_id, solar_w, load_w, grid_w, bat_w, bat_pct))

                # Upsert into cumulative_snapshots
                conn.execute("""
                    INSERT OR REPLACE INTO cumulative_snapshots
                    (timestamp, date, inverter_id, solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ts_str, today_str, inv_id, s_kwh, l_kwh, gi_kwh, ge_kwh, bc_kwh, bd_kwh))

            conn.commit()
            print(f"Successfully populated telemetry_history and cumulative_snapshots for {inv_id}!")
        finally:
            conn.close()

if __name__ == "__main__":
    backfill_today()
