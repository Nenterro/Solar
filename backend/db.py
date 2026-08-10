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
            CREATE TABLE IF NOT EXISTS cumulative_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                date TEXT NOT NULL,
                inverter_id TEXT NOT NULL,
                solar_kwh REAL DEFAULT 0.0,
                load_kwh REAL DEFAULT 0.0,
                grid_import_kwh REAL DEFAULT 0.0,
                grid_export_kwh REAL DEFAULT 0.0,
                battery_charge_kwh REAL DEFAULT 0.0,
                battery_discharge_kwh REAL DEFAULT 0.0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS automations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                time_of_day TEXT NOT NULL,
                inverter_id TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                actions TEXT NOT NULL,
                last_triggered TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inverter_settings_store (
                inverter_id TEXT NOT NULL,
                setting_key TEXT NOT NULL,
                setting_val REAL NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (inverter_id, setting_key)
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
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cum_time_inv 
            ON cumulative_snapshots (date, inverter_id, timestamp)
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
            conn.execute("DROP TABLE IF EXISTS cumulative_snapshots;")
            conn.execute("DROP TABLE IF EXISTS lifetime_baselines;")
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


def log_telemetry_snapshot(readings: Dict[str, Dict[str, Any]], bms_power_w: Optional[float] = None):
    """
    Log a 1-minute telemetry snapshot into sqlite telemetry_history table in local Pakistan Time (PKT).
    Format: YYYY-MM-DD HH:MM:SS
    """
    try:
        conn = get_db_connection()
        try:
            now_pkt = datetime.now(PKT)
            time_str = now_pkt.strftime("%Y-%m-%d %H:%M:%S")

            # Fetch REAL Battery SOC and Voltage from Knox BMS RS485
            bms_soc = None
            bms_v = None
            try:
                from battery_bms import bms
                bms_data = bms.get_latest_data()
                if bms_data.get("soc", 0) > 0:
                    bms_soc = float(bms_data["soc"])
                if bms_data.get("voltage", 0.0) > 0.0:
                    bms_v = float(bms_data["voltage"])
            except Exception:
                pass

            if bms_soc is None and hasattr(log_telemetry_snapshot, 'last_known_bms_soc'):
                bms_soc = log_telemetry_snapshot.last_known_bms_soc
            elif bms_soc is not None:
                log_telemetry_snapshot.last_known_bms_soc = bms_soc

            if bms_v is None and hasattr(log_telemetry_snapshot, 'last_known_bms_v'):
                bms_v = log_telemetry_snapshot.last_known_bms_v
            elif bms_v is not None:
                log_telemetry_snapshot.last_known_bms_v = bms_v

            # 1. Insert per-inverter rows
            valid_readings = {}
            for inv_id, r in readings.items():
                # Skip simulated/disconnected inverters — don't write zeros to DB
                if r.get("is_simulated", False) or not r.get("connected", True):
                    continue
                    
                solar_kw = r.get("solar_power_kw", 0.0)
                grid_kw = r.get("grid_power_kw", 0.0)
                bat_kw = r.get("battery_power_kw", 0.0)
                load_kw = r.get("ac_output_power_kw", 0.0)
                
                # STRICT DIRECTIVE: Use Knox BMS RS485 SOC & Voltage ONLY (never inverter wires!)
                soc_val = bms_soc if bms_soc is not None else 0.0
                bat_v = bms_v if bms_v is not None else 0.0
                
                # Modbus / Serial glitch filter (>100kW or SOC > 100% or battery_v > 70V is corrupted)
                if abs(solar_kw) > 100.0 or abs(grid_kw) > 100.0 or abs(bat_kw) > 100.0 or abs(load_kw) > 100.0 or soc_val > 100.0 or soc_val < 0.0 or bat_v > 70.0:
                    logger.warning(f"Outlier detected for {inv_id}: bat={bat_kw}, grid={grid_kw}, soc={soc_val}%, v={bat_v}V. Skipping.")
                    continue
                
                valid_readings[inv_id] = r
                clamped_soc = min(100.0, max(0.0, float(soc_val)))

                # Rate-of-change DB glitch suppression (SOC cannot jump > 5% in 1 minute)
                if not hasattr(log_telemetry_snapshot, 'last_db_soc'):
                    log_telemetry_snapshot.last_db_soc = {}
                
                prev_db_soc = log_telemetry_snapshot.last_db_soc.get(inv_id)
                if prev_db_soc is not None and abs(clamped_soc - prev_db_soc) > 5.0:
                    logger.warning(f"Telemetry DB log SOC glitch suppressed for {inv_id}: {clamped_soc}% vs last recorded {prev_db_soc}%. Using {prev_db_soc}%.")
                    clamped_soc = prev_db_soc
                else:
                    log_telemetry_snapshot.last_db_soc[inv_id] = clamped_soc

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
                    clamped_soc,
                    bat_v,
                    r.get("grid_voltage", 0.0),
                    r.get("inverter_temp_c", 0.0)
                ))

            # 2. Insert combined system total row ('all') with real averages
            readings_to_sum = valid_readings.values()
            
            if not readings_to_sum:
                conn.commit()
                return

            total_solar = sum(r.get("solar_power_kw", 0.0) * 1000.0 for r in readings_to_sum)
            total_load = sum(r.get("ac_output_power_kw", 0.0) * 1000.0 for r in readings_to_sum)
            total_grid = sum(r.get("grid_power_kw", 0.0) * 1000.0 for r in readings_to_sum)
            total_bat = sum(r.get("battery_power_kw", 0.0) * 1000.0 for r in readings_to_sum)
            
            socs = [r.get("battery_capacity_pct", 0.0) for r in readings_to_sum]
            avg_soc = sum(socs) / len(socs) if socs else 0.0
            
            bat_vs = [r.get("battery_voltage", 0.0) for r in readings_to_sum]
            avg_bat_v = sum(bat_vs) / len(bat_vs) if bat_vs else 0.0
            
            grid_vs = [r.get("grid_voltage", 0.0) for r in readings_to_sum]
            max_grid_v = max(grid_vs) if grid_vs else 0.0
            
            temps = [r.get("inverter_temp_c", 0.0) for r in readings_to_sum]
            avg_temp = sum(temps) / len(temps) if temps else 0.0

            conn.execute("""
                INSERT INTO telemetry_history 
                (timestamp, inverter_id, solar_w, load_w, grid_w, battery_w, battery_pct, battery_v, grid_v, temp_c)
                VALUES (?, 'all', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (time_str, total_solar, total_load, total_grid, total_bat, avg_soc, avg_bat_v, max_grid_v, avg_temp))

            if bms_power_w is not None:
                conn.execute("""
                    INSERT INTO telemetry_history 
                    (timestamp, inverter_id, solar_w, load_w, grid_w, battery_w, battery_pct, battery_v, grid_v, temp_c)
                    VALUES (?, 'bms', 0, 0, 0, ?, ?, ?, 0, ?)
                """, (time_str, float(bms_power_w), avg_soc, avg_bat_v, avg_temp))

            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error logging telemetry snapshot: {e}")


def query_bms_daily_totals(date_str: str) -> Dict[str, float]:
    """
    Calculate total kWh charged and total kWh discharged for a given date 
    directly from 1-minute BMS RS485 power readings in SQLite.
    """
    try:
        conn = get_db_connection()
        try:
            rows = conn.execute("""
                SELECT battery_w FROM telemetry_history
                WHERE timestamp LIKE ? AND inverter_id = 'bms'
            """, (f"{date_str}%",)).fetchall()
            
            if not rows:
                rows = conn.execute("""
                    SELECT battery_w FROM telemetry_history
                    WHERE timestamp LIKE ? AND inverter_id = 'all'
                """, (f"{date_str}%",)).fetchall()
            
            charge_wh = 0.0
            discharge_wh = 0.0
            for r in rows:
                w = float(r["battery_w"] or 0.0)
                if w > 0:
                    charge_wh += w / 60.0
                elif w < 0:
                    discharge_wh += abs(w) / 60.0
                    
            return {
                "date": date_str,
                "bms_charge_kwh": round(charge_wh / 1000.0, 2),
                "bms_discharge_kwh": round(discharge_wh / 1000.0, 2)
            }
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error computing BMS daily totals: {e}")
        return {"date": date_str, "bms_charge_kwh": 0.0, "bms_discharge_kwh": 0.0}


def update_lifetime_totals_and_calculate_daily(lifetime_readings: Dict[str, Dict[str, float]]):
    """
    Process raw accumulated lifetime energy kWh readings from inverters (QET, QLT, QGT, QFT, QCT).
    Establish start-of-day baseline if not present for today, calculate today's daily total as:
    Daily = max(0, Lifetime_Current - Lifetime_StartOfDay)
    and upsert into daily_totals table.
    """
    try:
        conn = get_db_connection()
        try:
            now_pkt = datetime.now(PKT)
            today_str = now_pkt.strftime("%Y-%m-%d")

            # Create baselines table if missing
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lifetime_baselines (
                    date TEXT NOT NULL,
                    inverter_id TEXT NOT NULL,
                    solar_start REAL DEFAULT 0.0,
                    load_start REAL DEFAULT 0.0,
                    grid_import_start REAL DEFAULT 0.0,
                    grid_export_start REAL DEFAULT 0.0,
                    battery_charge_start REAL DEFAULT 0.0,
                    battery_discharge_start REAL DEFAULT 0.0,
                    PRIMARY KEY (date, inverter_id)
                )
            """)

            daily_totals_calculated = {}

            for inv_id, r in lifetime_readings.items():
                curr_solar = float(r.get("solar") or 0.0)
                curr_load = float(r.get("load") or 0.0)
                curr_gi = float(r.get("grid_import") or 0.0)
                curr_ge = float(r.get("grid_export") or 0.0)
                curr_bc = float(r.get("battery_charge") or 0.0)
                curr_bd = float(r.get("battery_discharge") or 0.0)

                if curr_solar == 0.0 and curr_load == 0.0 and curr_gi == 0.0:
                    continue

                # Fetch or initialize start-of-day baseline
                base_row = conn.execute(
                    "SELECT * FROM lifetime_baselines WHERE date = ? AND inverter_id = ?",
                    (today_str, inv_id)
                ).fetchone()

                if not base_row:
                    conn.execute("""
                        INSERT OR REPLACE INTO lifetime_baselines
                        (date, inverter_id, solar_start, load_start, grid_import_start, grid_export_start, battery_charge_start, battery_discharge_start)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (today_str, inv_id, curr_solar, curr_load, curr_gi, curr_ge, curr_bc, curr_bd))
                    conn.commit()
                    
                    solar_start, load_start, gi_start, ge_start, bc_start, bd_start = (
                        curr_solar, curr_load, curr_gi, curr_ge, curr_bc, curr_bd
                    )
                else:
                    solar_start = base_row["solar_start"]
                    load_start = base_row["load_start"]
                    gi_start = base_row["grid_import_start"]
                    ge_start = base_row["grid_export_start"]
                    bc_start = base_row["battery_charge_start"]
                    bd_start = base_row["battery_discharge_start"]

                # Daily delta = max(0, curr - baseline)
                daily_s = max(0.0, round(curr_solar - solar_start, 1)) if (curr_solar - solar_start) <= 300.0 else 0.0
                daily_l = max(0.0, round(curr_load - load_start, 1)) if (curr_load - load_start) <= 300.0 else 0.0
                daily_gi = max(0.0, round(curr_gi - gi_start, 1)) if (curr_gi - gi_start) <= 300.0 else 0.0
                daily_ge = max(0.0, round(curr_ge - ge_start, 1)) if (curr_ge - ge_start) <= 300.0 else 0.0
                daily_bc = max(0.0, round(curr_bc - bc_start, 1)) if (curr_bc - bc_start) <= 300.0 else 0.0
                daily_bd = max(0.0, round(curr_bd - bd_start, 1)) if (curr_bd - bd_start) <= 300.0 else 0.0

                daily_totals_calculated[inv_id] = {
                    "solar": daily_s,
                    "load": daily_l,
                    "gridImport": daily_gi,
                    "gridExport": daily_ge,
                    "batteryCharge": daily_bc,
                    "batteryDischarge": daily_bd
                }

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
                """, (today_str, inv_id, daily_s, daily_l, daily_gi, daily_ge, daily_bc, daily_bd))

            # System aggregate ('all')
            if daily_totals_calculated:
                tot_s = round(sum(d["solar"] for d in daily_totals_calculated.values()), 1)
                tot_l = round(sum(d["load"] for d in daily_totals_calculated.values()), 1)
                tot_gi = round(sum(d["gridImport"] for d in daily_totals_calculated.values()), 1)
                tot_ge = round(sum(d["gridExport"] for d in daily_totals_calculated.values()), 1)
                tot_bc = round(sum(d["batteryCharge"] for d in daily_totals_calculated.values()), 1)
                tot_bd = round(sum(d["batteryDischarge"] for d in daily_totals_calculated.values()), 1)

                conn.execute("""
                    INSERT INTO daily_totals 
                    (date, inverter_id, solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh, updated_at)
                    VALUES (?, 'all', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(date, inverter_id) DO UPDATE SET
                        solar_kwh=excluded.solar_kwh,
                        load_kwh=excluded.load_kwh,
                        grid_import_kwh=excluded.grid_import_kwh,
                        grid_export_kwh=excluded.grid_export_kwh,
                        battery_charge_kwh=excluded.battery_charge_kwh,
                        battery_discharge_kwh=excluded.battery_discharge_kwh,
                        updated_at=CURRENT_TIMESTAMP
                """, (today_str, tot_s, tot_l, tot_gi, tot_ge, tot_bc, tot_bd))

            conn.commit()
            logger.info(f"Updated lifetime-based daily totals for {today_str}: {len(daily_totals_calculated)} inverters")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error updating lifetime-based daily totals: {e}")


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


def get_combined_daily_total(date_str: str, inverter_id: str = "all") -> Dict[str, Any]:
    """
    Returns the daily total for a given date by combining:
    1. Hardware lifetime register delta (from daily_totals table)
    2. 1-minute power integration (from telemetry_history table)
    Filters out any corrupt/inflated baseline jumps > 100.0 kWh (or > 35.0 kWh per single inverter)
    and prefers the 1-minute power integration total if hardware value is suspiciously inflated.
    """
    try:
        conn = get_db_connection()
        try:
            # Maximum physical ceiling per day (kWh)
            max_daily_cap = 100.0 if inverter_id == "all" else 35.0

            # 1. Fetch hardware daily total from daily_totals table
            row = conn.execute("""
                SELECT solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh
                FROM daily_totals
                WHERE date = ? AND inverter_id = ?
            """, (date_str, inverter_id)).fetchone()

            hw_s = round(row["solar_kwh"], 2) if row else 0.0
            hw_l = round(row["load_kwh"], 2) if row else 0.0
            hw_gi = round(row["grid_import_kwh"], 2) if row else 0.0
            hw_ge = round(row["grid_export_kwh"], 2) if row else 0.0
            hw_bc = round(row["battery_charge_kwh"], 2) if row else 0.0
            hw_bd = round(row["battery_discharge_kwh"], 2) if row else 0.0

            # Discard inflated hardware register jumps above max physical ceiling
            if hw_s > max_daily_cap: hw_s = 0.0
            if hw_l > max_daily_cap: hw_l = 0.0
            if hw_gi > max_daily_cap: hw_gi = 0.0
            if hw_ge > max_daily_cap: hw_ge = 0.0
            if hw_bc > max_daily_cap: hw_bc = 0.0
            if hw_bd > max_daily_cap: hw_bd = 0.0

            # 2. Integrate 1-minute telemetry_history power samples
            t_rows = conn.execute("""
                SELECT solar_w, load_w, grid_w, battery_w
                FROM telemetry_history
                WHERE timestamp LIKE ? AND inverter_id = ?
            """, (f"{date_str}%", inverter_id)).fetchall()

            int_s, int_l, int_gi, int_ge, int_bc, int_bd = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            if t_rows:
                for r in t_rows:
                    s_kw = max(0.0, r["solar_w"] / 1000.0)
                    l_kw = max(0.0, r["load_w"] / 1000.0)
                    g_kw = r["grid_w"] / 1000.0
                    b_kw = r["battery_w"] / 1000.0

                    int_s += s_kw / 60.0
                    int_l += l_kw / 60.0
                    if g_kw > 0: int_gi += g_kw / 60.0
                    else: int_ge += abs(g_kw) / 60.0

                    if b_kw > 0: int_bc += b_kw / 60.0
                    else: int_bd += abs(b_kw) / 60.0

            # If 1-minute integrated total exists, prefer it if hardware value is zero or suspiciously inflated (> 1.5x int)
            if int_s > 0:
                final_s = int_s if (hw_s == 0.0 or hw_s > int_s * 1.5) else max(hw_s, int_s)
            else:
                final_s = hw_s

            if int_l > 0:
                final_l = int_l if (hw_l == 0.0 or hw_l > int_l * 1.5) else max(hw_l, int_l)
            else:
                final_l = hw_l

            if int_gi > 0:
                final_gi = int_gi if (hw_gi == 0.0 or hw_gi > int_gi * 1.5) else max(hw_gi, int_gi)
            else:
                final_gi = hw_gi

            if int_ge > 0:
                final_ge = int_ge if (hw_ge == 0.0 or hw_ge > int_ge * 1.5) else max(hw_ge, int_ge)
            else:
                final_ge = hw_ge

            if int_bc > 0:
                final_bc = int_bc if (hw_bc == 0.0 or hw_bc > int_bc * 1.5) else max(hw_bc, int_bc)
            else:
                final_bc = hw_bc

            if int_bd > 0:
                final_bd = int_bd if (hw_bd == 0.0 or hw_bd > int_bd * 1.5) else max(hw_bd, int_bd)
            else:
                final_bd = hw_bd

            return {
                "time": date_str,
                "solar": round(final_s, 1),
                "load": round(final_l, 1),
                "gridImport": round(final_gi, 1),
                "gridExport": round(final_ge, 1),
                "batteryCharge": round(final_bc, 1),
                "batteryDischarge": round(final_bd, 1)
            }
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error computing combined daily total: {e}")
        return {
            "time": date_str, "solar": 0.0, "load": 0.0, "gridImport": 0.0,
            "gridExport": 0.0, "batteryCharge": 0.0, "batteryDischarge": 0.0
        }


def query_daily_totals_for_month(year_month: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
    """
    Query daily totals strictly from local SQLite DB for a given month (YYYY-MM).
    Combines hardware lifetime deltas and 1-minute power integration with outlier rejection.
    """
    try:
        conn = get_db_connection()
        try:
            # Find all dates recorded in daily_totals or telemetry_history for year_month
            rows = conn.execute("""
                SELECT DISTINCT date FROM (
                    SELECT date FROM daily_totals WHERE date LIKE ? AND inverter_id = ?
                    UNION
                    SELECT substr(timestamp, 1, 10) as date FROM telemetry_history WHERE timestamp LIKE ? AND inverter_id = ?
                ) ORDER BY date ASC
            """, (f"{year_month}%", inverter_id, f"{year_month}%", inverter_id)).fetchall()

            res = []
            for r in rows:
                d_str = r["date"]
                if not d_str: continue
                tot = get_combined_daily_total(d_str, inverter_id)
                res.append(tot)
            return res
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying monthly daily_totals: {e}")
        return []


def query_daily_totals_for_day(date_str: str, inverter_id: str = "all") -> Optional[Dict[str, Any]]:
    """
    Query daily total strictly from local SQLite DB for a single day (YYYY-MM-DD).
    """
    return get_combined_daily_total(date_str, inverter_id)


def query_daily_totals_for_year(year_str: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
    """
    Query monthly aggregated totals strictly from local SQLite DB for a given year (YYYY).
    Aggregates from sanitized monthly daily totals.
    """
    try:
        conn = get_db_connection()
        try:
            # Query all recorded months in the given year
            month_rows = conn.execute("""
                SELECT DISTINCT strftime('%Y-%m', date) as m_str
                FROM daily_totals
                WHERE date LIKE ? AND inverter_id = ?
                ORDER BY m_str ASC
            """, (f"{year_str}%", inverter_id)).fetchall()

            res = []
            for m in month_rows:
                m_str = m["m_str"]
                if not m_str: continue
                month_days = query_daily_totals_for_month(m_str, inverter_id)
                if not month_days: continue

                m_solar = round(sum(d.get("solar", 0.0) for d in month_days), 1)
                m_load = round(sum(d.get("load", 0.0) for d in month_days), 1)
                m_gi = round(sum(d.get("gridImport", 0.0) for d in month_days), 1)
                m_ge = round(sum(d.get("gridExport", 0.0) for d in month_days), 1)
                m_bc = round(sum(d.get("batteryCharge", 0.0) for d in month_days), 1)
                m_bd = round(sum(d.get("batteryDischarge", 0.0) for d in month_days), 1)

                if m_solar == 0.0 and m_load == 0.0 and m_gi == 0.0 and m_ge == 0.0:
                    continue

                res.append({
                    "time": m_str,
                    "solar": m_solar,
                    "load": m_load,
                    "gridImport": m_gi,
                    "gridExport": m_ge,
                    "batteryCharge": m_bc,
                    "batteryDischarge": m_bd,
                })
            return res
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying yearly totals: {e}")
        return []





def query_daily_history(date_str: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
    """
    Query 1-minute telemetry history for Graphs Page.
    STRICT DIRECTIVE: Always uses Knox BMS RS485 SOC for batteryLevel across all inverter selections (all, inv1, inv2, inv3).
    """
    try:
        conn = get_db_connection()
        try:
            # Build 1-minute lookup map for Knox BMS RS485 SOC for this day (from 'all' rows)
            bms_soc_map = {}
            bms_rows = conn.execute("""
                SELECT timestamp, battery_pct
                FROM telemetry_history
                WHERE timestamp LIKE ? AND inverter_id = 'all'
                ORDER BY timestamp ASC
            """, (f"{date_str}%",)).fetchall()
            for br in bms_rows:
                ts_str = br["timestamp"]
                t_key = ts_str[11:16] if len(ts_str) >= 16 else ts_str
                if br["battery_pct"] and br["battery_pct"] > 0:
                    bms_soc_map[t_key] = br["battery_pct"]

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

                # STRICT: Prefer Knox BMS RS485 SOC for battery level
                raw_soc = bms_soc_map.get(time_label, float(r["battery_pct"] or 0.0))
                if abs(solar_kw) > 100.0 or abs(load_kw) > 100.0 or abs(grid_kw) > 100.0 or abs(bat_kw) > 100.0 or raw_soc > 100.0:
                    continue

                clamped_soc = min(100.0, max(0.0, raw_soc))

                results.append({
                    "time": time_label,
                    "solar": max(0.0, solar_kw),
                    "load": max(0.0, load_kw),
                    "gridImport": max(0.0, grid_kw),
                    "gridExport": abs(min(0.0, grid_kw)),
                    "batteryCharge": max(0.0, bat_kw),
                    "batteryDischarge": abs(min(0.0, bat_kw)),
                    "batteryLevel": clamped_soc,
                    "gridActive": r["grid_v"] > 90.0
                })

            return results
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying history: {e}")
        return []


def save_cumulative_snapshot(date_str: str, timestamp_str: str, inverter_id: str, r: Dict[str, float]):
    """
    Log or update a 10-minute cumulative daily kWh snapshot into cumulative_snapshots table.
    """
    try:
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO cumulative_snapshots
                (timestamp, date, inverter_id, solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp_str, date_str, inverter_id,
                round(float(r.get("solar", 0.0)), 2),
                round(float(r.get("load", 0.0)), 2),
                round(float(r.get("gridImport", 0.0)), 2),
                round(float(r.get("gridExport", 0.0)), 2),
                round(float(r.get("batteryCharge", 0.0)), 2),
                round(float(r.get("batteryDischarge", 0.0)), 2)
            ))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error saving cumulative snapshot: {e}")

def query_cumulative_history(date_str: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
    """
    Cumulative Intraday Graph Endpoint.
    Uses the current value of the daily total (calculated from lifetime differences)
    to render the cumulative intraday accumulation curve.
    """
    try:
        conn = get_db_connection()
        try:
            # 1. Fetch current calculated daily total for the day
            day_tot = query_daily_totals_for_day(date_str, inverter_id)
            
            tot_solar = day_tot.get("solar", 0.0) if day_tot else 0.0
            tot_load = day_tot.get("load", 0.0) if day_tot else 0.0
            tot_gi = day_tot.get("gridImport", 0.0) if day_tot else 0.0
            tot_ge = day_tot.get("gridExport", 0.0) if day_tot else 0.0
            tot_bc = day_tot.get("batteryCharge", 0.0) if day_tot else 0.0
            tot_bd = day_tot.get("batteryDischarge", 0.0) if day_tot else 0.0

            # 2. Fetch 1-minute telemetry history points for the day to format the timeline
            t_rows = conn.execute("""
                SELECT timestamp, solar_w, load_w, grid_w, battery_w, battery_pct
                FROM telemetry_history
                WHERE timestamp LIKE ? AND inverter_id = ?
                ORDER BY timestamp ASC
            """, (f"{date_str}%", inverter_id)).fetchall()

            if t_rows:
                results = [{
                    "time": "00:00",
                    "solar": 0.0, "load": 0.0, "gridImport": 0.0,
                    "gridExport": 0.0, "batteryCharge": 0.0, "batteryDischarge": 0.0,
                    "batteryLevel": t_rows[0]["battery_pct"] if t_rows else 0.0
                }]
                
                # Accumulate energy using 1-minute power integration
                cum_s, cum_l, cum_gi, cum_ge, cum_bc, cum_bd = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                total_count = len(t_rows)
                
                for idx, r in enumerate(t_rows):
                    s_kw = max(0.0, r["solar_w"] / 1000.0)
                    l_kw = max(0.0, r["load_w"] / 1000.0)
                    g_kw = r["grid_w"] / 1000.0
                    b_kw = r["battery_w"] / 1000.0

                    cum_s += s_kw / 60.0
                    cum_l += l_kw / 60.0
                    if g_kw > 0: cum_gi += g_kw / 60.0
                    else: cum_ge += abs(g_kw) / 60.0

                    if b_kw > 0: cum_bc += b_kw / 60.0
                    else: cum_bd += abs(b_kw) / 60.0

                    ts_str = r["timestamp"]
                    time_label = ts_str[11:16] if len(ts_str) >= 16 else ts_str
                    
                    if time_label != "00:00":
                        results.append({
                            "time": time_label,
                            "solar": round(cum_s, 2),
                            "load": round(cum_l, 2),
                            "gridImport": round(cum_gi, 2),
                            "gridExport": round(cum_ge, 2),
                            "batteryCharge": round(cum_bc, 2),
                            "batteryDischarge": round(cum_bd, 2),
                            "batteryLevel": r["battery_pct"]
                        })
                return results

            # 3. If no 1-minute history yet, generate points up to current time ending at current daily total
            now_pkt = datetime.now(PKT)
            today_str = now_pkt.strftime("%Y-%m-%d")
            
            if date_str == today_str:
                max_minutes = now_pkt.hour * 60 + now_pkt.minute + 1
            else:
                max_minutes = 1440

            results = []
            for m in range(0, max_minutes, 10):
                h = m // 60
                mn = m % 60
                time_label = f"{h:02d}:{mn:02d}"
                frac = min(1.0, m / max(1, max_minutes - 10))

                results.append({
                    "time": time_label,
                    "solar": round(tot_solar * frac, 2),
                    "load": round(tot_load * frac, 2),
                    "gridImport": round(tot_gi * frac, 2),
                    "gridExport": round(tot_ge * frac, 2),
                    "batteryCharge": round(tot_bc * frac, 2),
                    "batteryDischarge": round(tot_bd * frac, 2),
                    "batteryLevel": 100
                })

            return results
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying cumulative history: {e}")
        return []


def update_hardware_daily_totals(inv_id: str, hw_totals: Dict[str, float]):
    """
    Updates the daily totals directly from the hardware's daily energy registers.
    """
    try:
        now_pkt = datetime.now(PKT)
        date_str = now_pkt.strftime("%Y-%m-%d")
        ts_1m = now_pkt.strftime("%Y-%m-%d %H:%M:00")
        
        conn = get_db_connection()
        try:
            s_kwh = hw_totals.get('solar', 0.0)
            l_kwh = hw_totals.get('load', 0.0)
            gi_kwh = hw_totals.get('grid_import', 0.0)
            ge_kwh = hw_totals.get('grid_export', 0.0)
            bc_kwh = hw_totals.get('battery_charge', 0.0)
            bd_kwh = hw_totals.get('battery_discharge', 0.0)
            
            # Fetch previous to prevent overwriting with 0 if hardware read failed
            cursor = conn.cursor()
            cursor.execute("""
                SELECT solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh
                FROM daily_totals
                WHERE date = ? AND inverter_id = ?
            """, (date_str, inv_id))
            prev = cursor.fetchone()
            
            if prev:
                if s_kwh == 0.0: s_kwh = prev["solar_kwh"]
                if l_kwh == 0.0: l_kwh = prev["load_kwh"]
                if gi_kwh == 0.0: gi_kwh = prev["grid_import_kwh"]
                if ge_kwh == 0.0: ge_kwh = prev["grid_export_kwh"]
                if bc_kwh == 0.0: bc_kwh = prev["battery_charge_kwh"]
                if bd_kwh == 0.0: bd_kwh = prev["battery_discharge_kwh"]

            # Update daily_totals
            conn.execute("""
                INSERT OR REPLACE INTO daily_totals 
                (date, inverter_id, solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (date_str, inv_id, s_kwh, l_kwh, gi_kwh, ge_kwh, bc_kwh, bd_kwh))
            
            # Save 1-minute snapshot for cumulative graph
            conn.execute("""
                INSERT OR REPLACE INTO cumulative_snapshots
                (timestamp, date, inverter_id, solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ts_1m, date_str, inv_id, s_kwh, l_kwh, gi_kwh, ge_kwh, bc_kwh, bd_kwh))
            
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error updating hardware daily totals: {e}")


# --- AUTOMATION & TIMER DB FUNCTIONS ---

def query_automations() -> List[Dict[str, Any]]:
    """Retrieve all configured automations."""
    try:
        conn = get_db_connection()
        try:
            rows = conn.execute("""
                SELECT id, name, time_of_day, inverter_id, enabled, actions, last_triggered, created_at
                FROM automations
                ORDER BY time_of_day ASC
            """).fetchall()

            res = []
            for r in rows:
                try:
                    actions_list = json.loads(r["actions"])
                except Exception:
                    actions_list = []

                res.append({
                    "id": r["id"],
                    "name": r["name"],
                    "time_of_day": r["time_of_day"],
                    "inverter_id": r["inverter_id"],
                    "enabled": bool(r["enabled"]),
                    "actions": actions_list,
                    "last_triggered": r["last_triggered"],
                    "created_at": r["created_at"]
                })
            return res
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying automations: {e}")
        return []


def save_automation(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create or update an automation record."""
    try:
        conn = get_db_connection()
        try:
            auto_id = data.get("id") or f"auto_{int(datetime.now().timestamp()*1000)}"
            name = data.get("name", "Scheduled Inverter Control")
            time_of_day = data.get("time_of_day", "08:00")
            inverter_id = data.get("inverter_id", "all")
            enabled = 1 if data.get("enabled", True) else 0
            actions = json.dumps(data.get("actions", []))

            conn.execute("""
                INSERT INTO automations (id, name, time_of_day, inverter_id, enabled, actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    time_of_day=excluded.time_of_day,
                    inverter_id=excluded.inverter_id,
                    enabled=excluded.enabled,
                    actions=excluded.actions
            """, (auto_id, name, time_of_day, inverter_id, enabled, actions))

            conn.commit()
            logger.info(f"Saved automation {auto_id} ('{name}') for {time_of_day}")
            return {
                "id": auto_id,
                "name": name,
                "time_of_day": time_of_day,
                "inverter_id": inverter_id,
                "enabled": bool(enabled),
                "actions": data.get("actions", [])
            }
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error saving automation: {e}")
        return None


def delete_automation(auto_id: str) -> bool:
    """Delete an automation record by ID."""
    try:
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM automations WHERE id = ?", (auto_id,))
            conn.commit()
            logger.info(f"Deleted automation {auto_id}")
            return True
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error deleting automation: {e}")
        return False


def toggle_automation(auto_id: str) -> Optional[bool]:
    """Toggle enabled status of an automation."""
    try:
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT enabled FROM automations WHERE id = ?", (auto_id,)).fetchone()
            if not row:
                return None
            new_state = 0 if row["enabled"] else 1
            conn.execute("UPDATE automations SET enabled = ? WHERE id = ?", (new_state, auto_id))
            conn.commit()
            return bool(new_state)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error toggling automation: {e}")
        return None


def get_due_automations(current_time_hhmm: str, current_date_str: str) -> List[Dict[str, Any]]:
    """
    Get enabled automations due at current_time_hhmm that haven't been triggered yet today.
    """
    try:
        conn = get_db_connection()
        try:
            trigger_stamp = f"{current_date_str} {current_time_hhmm}"
            rows = conn.execute("""
                SELECT id, name, time_of_day, inverter_id, actions, last_triggered
                FROM automations
                WHERE enabled = 1 
                  AND time_of_day = ? 
                  AND (last_triggered IS NULL OR last_triggered != ?)
            """, (current_time_hhmm, trigger_stamp)).fetchall()

            due = []
            for r in rows:
                try:
                    actions_list = json.loads(r["actions"])
                except Exception:
                    actions_list = []

                due.append({
                    "id": r["id"],
                    "name": r["name"],
                    "time_of_day": r["time_of_day"],
                    "inverter_id": r["inverter_id"],
                    "actions": actions_list
                })

                # Mark triggered stamp immediately
                conn.execute("UPDATE automations SET last_triggered = ? WHERE id = ?", (trigger_stamp, r["id"]))

            conn.commit()
            return due
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error getting due automations: {e}")
        return []


def save_inverter_setting_override(inverter_id: str, setting_key: str, setting_val: float):
    """Save/update a voltage setting override in SQLite DB."""
    try:
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO inverter_settings_store (inverter_id, setting_key, setting_val, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(inverter_id, setting_key) DO UPDATE SET
                    setting_val=excluded.setting_val,
                    updated_at=CURRENT_TIMESTAMP
            """, (inverter_id, setting_key, float(setting_val)))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error saving setting override for {inverter_id} ({setting_key}): {e}")


def get_inverter_setting_override(inverter_id: str, setting_key: str, default_val: float) -> float:
    """Retrieve saved voltage setting override from SQLite DB or return default_val."""
    try:
        conn = get_db_connection()
        try:
            row = conn.execute("""
                SELECT setting_val FROM inverter_settings_store
                WHERE inverter_id = ? AND setting_key = ?
            """, (inverter_id, setting_key)).fetchone()
            if row and row["setting_val"] is not None:
                return float(row["setting_val"])
            return default_val
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error getting setting override for {inverter_id} ({setting_key}): {e}")
        return default_val
