import os
import sqlite3
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("SOLAR_DB")
DB_PATH = os.path.join(os.path.dirname(__file__), "solar.db")

# Pakistan Standard Time (PKT = UTC+5)
PKT = timezone(timedelta(hours=5))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    """
    Initialize SQLite database tables for real-time telemetry, 1-minute history, and daily totals.
    Called once at module load time.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS realtime (
                id TEXT PRIMARY KEY,
                payload TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                inverter_id TEXT NOT NULL,
                solar_w REAL DEFAULT 0.0,
                load_w REAL DEFAULT 0.0,
                grid_w REAL DEFAULT 0.0,
                battery_w REAL DEFAULT 0.0,
                battery_pct REAL DEFAULT 0.0,
                battery_v REAL DEFAULT 0.0,
                grid_v REAL DEFAULT 0.0,
                temp_c REAL DEFAULT 0.0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_totals (
                date TEXT NOT NULL,
                inverter_id TEXT NOT NULL,
                solar_kwh REAL DEFAULT 0.0,
                load_kwh REAL DEFAULT 0.0,
                grid_import_kwh REAL DEFAULT 0.0,
                grid_export_kwh REAL DEFAULT 0.0,
                battery_charge_kwh REAL DEFAULT 0.0,
                battery_discharge_kwh REAL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, inverter_id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_telemetry_time_inv 
            ON telemetry_history (timestamp, inverter_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_totals_date_inv 
            ON daily_totals (date, inverter_id)
        """)

        conn.commit()
        conn.close()
        logger.info(f"Database initialized successfully at {DB_PATH}")
    except Exception as e:
        logger.error(f"Error initializing DB: {e}")

# Call init_db once at module load time
init_db()


def nuke_db():
    """Forcefully drop and recreate all tables in SQLite DB."""
    try:
        conn = get_db_connection()
        try:
            conn.execute("DROP TABLE IF EXISTS telemetry_history;")
            conn.execute("DROP TABLE IF EXISTS daily_totals;")
            conn.execute("DROP TABLE IF EXISTS realtime;")
            conn.commit()
        finally:
            conn.close()
        init_db()
        logger.info("Database completely nuked and recreated clean.")
        return True
    except Exception as e:
        logger.error(f"Error nuking database: {e}")
        return False


def reset_db_history():
    """Purge all old telemetry history and daily totals from database."""
    return nuke_db()


def update_realtime(inverter_id: str, payload: Dict[str, Any]):
    """Save or replace the latest realtime telemetry payload."""
    try:
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO realtime (id, payload, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (f"latest_{inverter_id}", json.dumps(payload))
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error updating realtime: {e}")


def log_telemetry_snapshot(readings: Dict[str, Dict[str, Any]]):
    """
    Log a 1-minute telemetry snapshot into sqlite telemetry_history table in local Pakistan Time (PKT).
    Format: YYYY-MM-DD HH:MM:SS
    """
    try:
        conn = get_db_connection()
        try:
            now_pkt = datetime.now(PKT)
            time_str = now_pkt.strftime("%Y-%m-%d %H:%M:%S")

            # 1. Insert per-inverter rows
            for inv_id, r in readings.items():
                conn.execute("""
                    INSERT INTO telemetry_history 
                    (timestamp, inverter_id, solar_w, load_w, grid_w, battery_w, battery_pct, battery_v, grid_v, temp_c)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    time_str,
                    inv_id,
                    r.get("solar_power_kw", 0.0) * 1000.0,
                    r.get("ac_output_power_kw", 0.0) * 1000.0,
                    r.get("grid_power_kw", 0.0) * 1000.0,
                    r.get("battery_power_kw", 0.0) * 1000.0,
                    r.get("battery_capacity_pct", 0.0),
                    r.get("battery_voltage", 0.0),
                    r.get("grid_voltage", 0.0),
                    r.get("inverter_temp_c", 0.0)
                ))

            # 2. Insert combined system total row ('all') with real averages
            total_solar = sum(r.get("solar_power_kw", 0.0) * 1000.0 for r in readings.values())
            total_load = sum(r.get("ac_output_power_kw", 0.0) * 1000.0 for r in readings.values())
            total_grid = sum(r.get("grid_power_kw", 0.0) * 1000.0 for r in readings.values())
            total_bat = sum(r.get("battery_power_kw", 0.0) * 1000.0 for r in readings.values())
            
            socs = [r.get("battery_capacity_pct", 0.0) for r in readings.values()]
            avg_soc = sum(socs) / len(socs) if socs else 0.0
            
            bat_vs = [r.get("battery_voltage", 0.0) for r in readings.values()]
            avg_bat_v = sum(bat_vs) / len(bat_vs) if bat_vs else 0.0
            
            grid_vs = [r.get("grid_voltage", 0.0) for r in readings.values()]
            avg_grid_v = sum(grid_vs) / len(grid_vs) if grid_vs else 0.0
            
            temps = [r.get("inverter_temp_c", 0.0) for r in readings.values()]
            avg_temp = sum(temps) / len(temps) if temps else 0.0

            conn.execute("""
                INSERT INTO telemetry_history 
                (timestamp, inverter_id, solar_w, load_w, grid_w, battery_w, battery_pct, battery_v, grid_v, temp_c)
                VALUES (?, 'all', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (time_str, total_solar, total_load, total_grid, total_bat, avg_soc, avg_bat_v, avg_grid_v, avg_temp))

            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error logging telemetry snapshot: {e}")


def save_daily_totals(records: List[Dict[str, Any]], inverter_id: str = "all"):
    """
    Upsert scraped DESSMonitor daily totals into SQLite daily_totals table.
    Filters outlier values > 300 kWh at ingestion time.
    """
    try:
        conn = get_db_connection()
        try:
            saved_count = 0
            for r in records:
                d_str = r.get("time")  # YYYY-MM-DD
                if not d_str or len(d_str) < 10:
                    continue

                solar_val = float(r.get("solar") or 0.0)
                grid_imp_val = float(r.get("gridImport") or 0.0)

                # Filter outlier registers (Day 1 cumulative corruption)
                if solar_val > 300.0 or grid_imp_val > 300.0:
                    continue

                conn.execute("""
                    INSERT INTO daily_totals 
                    (date, inverter_id, solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(date, inverter_id) DO UPDATE SET
                        solar_kwh=excluded.solar_kwh,
                        load_kwh=excluded.load_kwh,
                        grid_import_kwh=excluded.grid_import_kwh,
                        grid_export_kwh=excluded.grid_export_kwh,
                        battery_charge_kwh=excluded.battery_charge_kwh,
                        battery_discharge_kwh=excluded.battery_discharge_kwh,
                        updated_at=CURRENT_TIMESTAMP
                """, (
                    d_str,
                    inverter_id,
                    solar_val,
                    float(r.get("load") or 0.0),
                    grid_imp_val,
                    float(r.get("gridExport") or 0.0),
                    float(r.get("batteryCharge") or 0.0),
                    float(r.get("batteryDischarge") or 0.0)
                ))
                saved_count += 1
            conn.commit()
            logger.info(f"Saved {saved_count} daily total records to SQLite for inverter '{inverter_id}'")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error saving daily totals: {e}")


def query_daily_totals_for_month(year_month: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
    """
    Query daily totals strictly from local SQLite DB for a given month (YYYY-MM).
    Does NOT auto-fetch cloud data. Filtering is minimal since outliers are already
    filtered at ingestion time in save_daily_totals().
    """
    try:
        conn = get_db_connection()
        try:
            rows = conn.execute("""
                SELECT date, solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh
                FROM daily_totals
                WHERE date LIKE ? AND inverter_id = ?
                ORDER BY date ASC
            """, (f"{year_month}%", inverter_id)).fetchall()

            res = []
            for r in rows:
                s = round(r["solar_kwh"], 1)
                l = round(r["load_kwh"], 1)
                gi = round(r["grid_import_kwh"], 1)
                ge = round(r["grid_export_kwh"], 1)
                bc = round(r["battery_charge_kwh"], 1)
                bd = round(r["battery_discharge_kwh"], 1)

                # Skip empty zero rows only
                if s == 0.0 and l == 0.0 and gi == 0.0 and ge == 0.0 and bc == 0.0 and bd == 0.0:
                    continue

                res.append({
                    "time": r["date"],
                    "solar": s,
                    "load": l,
                    "gridImport": gi,
                    "gridExport": ge,
                    "batteryCharge": bc,
                    "batteryDischarge": bd,
                })
            return res
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying monthly daily_totals: {e}")
        return []


def query_daily_totals_for_year(year_str: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
    """
    Query monthly aggregated totals strictly from local SQLite DB for a given year (YYYY).
    """
    try:
        conn = get_db_connection()
        try:
            rows = conn.execute("""
                SELECT strftime('%Y-%m', date) as m_str,
                       SUM(solar_kwh) as solar,
                       SUM(load_kwh) as load,
                       SUM(grid_import_kwh) as gridImport,
                       SUM(grid_export_kwh) as gridExport,
                       SUM(battery_charge_kwh) as batteryCharge,
                       SUM(battery_discharge_kwh) as batteryDischarge
                FROM daily_totals
                WHERE date LIKE ? AND inverter_id = ?
                GROUP BY m_str
                ORDER BY m_str ASC
            """, (f"{year_str}%", inverter_id)).fetchall()

            res = []
            for r in rows:
                s = round(r["solar"] or 0.0, 1)
                l = round(r["load"] or 0.0, 1)
                gi = round(r["gridImport"] or 0.0, 1)
                ge = round(r["gridExport"] or 0.0, 1)
                bc = round(r["batteryCharge"] or 0.0, 1)
                bd = round(r["batteryDischarge"] or 0.0, 1)

                if s == 0.0 and l == 0.0 and gi == 0.0 and ge == 0.0 and bc == 0.0 and bd == 0.0:
                    continue

                res.append({
                    "time": r["m_str"],
                    "solar": s,
                    "load": l,
                    "gridImport": gi,
                    "gridExport": ge,
                    "batteryCharge": bc,
                    "batteryDischarge": bd,
                })
            return res
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying yearly totals: {e}")
        return []


def query_daily_totals_for_day(date_str: str, inverter_id: str = "all") -> Optional[Dict[str, Any]]:
    """
    Query daily total strictly from local SQLite DB for a single day (YYYY-MM-DD).
    """
    try:
        conn = get_db_connection()
        try:
            row = conn.execute("""
                SELECT date, solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh
                FROM daily_totals
                WHERE date = ? AND inverter_id = ?
            """, (date_str, inverter_id)).fetchone()

            if row:
                return {
                    "time": row["date"],
                    "solar": round(row["solar_kwh"], 1),
                    "load": round(row["load_kwh"], 1),
                    "gridImport": round(row["grid_import_kwh"], 1),
                    "gridExport": round(row["grid_export_kwh"], 1),
                    "batteryCharge": round(row["battery_charge_kwh"], 1),
                    "batteryDischarge": round(row["battery_discharge_kwh"], 1),
                }
            return None
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying single daily total: {e}")
        return None


def query_daily_history(date_str: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
    """
    Query 1-minute telemetry history for Graphs Page.
    Returns ONLY points that actually exist in the database — no zero-padding.
    The frontend graph scales its X-axis dynamically based on the returned data range.
    """
    try:
        conn = get_db_connection()
        try:
            rows = conn.execute("""
                SELECT timestamp, solar_w, load_w, grid_w, battery_w, battery_pct, grid_v
                FROM telemetry_history
                WHERE timestamp LIKE ? AND inverter_id = ?
                ORDER BY timestamp ASC
            """, (f"{date_str}%", inverter_id)).fetchall()

            results = []
            for r in rows:
                ts_str = r["timestamp"]  # "YYYY-MM-DD HH:MM:SS"
                time_label = ts_str[11:16] if len(ts_str) >= 16 else ts_str

                solar_kw = round(r["solar_w"] / 1000.0, 2)
                load_kw = round(r["load_w"] / 1000.0, 2)
                grid_kw = round(r["grid_w"] / 1000.0, 2)
                bat_kw = round(r["battery_w"] / 1000.0, 2)

                results.append({
                    "time": time_label,
                    "solar": max(0.0, solar_kw),
                    "load": max(0.0, load_kw),
                    "gridImport": max(0.0, grid_kw),
                    "gridExport": abs(min(0.0, grid_kw)),
                    "batteryCharge": max(0.0, bat_kw),
                    "batteryDischarge": abs(min(0.0, bat_kw)),
                    "batteryLevel": r["battery_pct"],
                    "gridActive": r["grid_v"] > 90.0
                })

            return results
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying history: {e}")
        return []

