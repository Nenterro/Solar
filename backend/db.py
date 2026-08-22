import os
import shutil
import sqlite3
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("SOLAR_DB")
DB_PATH = os.path.join(os.path.dirname(__file__), "solar.db")

# Pakistan Standard Time (PKT = UTC+5)
PKT = timezone(timedelta(hours=5))

# Fallback sampling period, in seconds, used only when a day has a single
# sample and no gap can be measured.
NOMINAL_SAMPLE_SECONDS = 60.0

# Longest gap between two consecutive samples that is still treated as
# continuous operation. Anything larger is backend downtime, and the missing
# energy is not extrapolated across the hole. This has to sit above the
# 10-minute cadence of DESS-backfilled days, or those days read low.
MAX_GAP_SECONDS = 900.0

# Physical daily ceilings (kWh). These exist ONLY to reject corrupt register
# reads, not to second-guess good ones -- each inverter is rated 15 kW, so a
# real day can never approach these. They must stay well above the true maximum
# daily yield or legitimate hardware totals get discarded (this was the cause of
# the inflated totals reported on 2026-08-22).
MAX_DAILY_KWH_PER_INVERTER = 150.0
MAX_DAILY_KWH_ALL = 450.0

# Fraction of a day's minutes that must carry a telemetry sample before the
# 1-minute integration is considered a complete record of that day.
MIN_INTEGRATION_COVERAGE = 0.90

# Largest plausible single-day jump in a lifetime register. A single inverter
# cannot exceed its own daily ceiling, so reuse that rather than a looser value:
# a stale or corrupt baseline otherwise yields a "day" of several hundred kWh
# that is still small enough to pass a laxer check.
MAX_LIFETIME_DELTA_KWH = MAX_DAILY_KWH_PER_INVERTER

# Days of 1-minute telemetry to retain. 0 keeps everything. Daily/monthly/yearly
# figures live in daily_totals and are never purged by this.
TELEMETRY_RETENTION_DAYS = int(os.getenv("SOLAR_TELEMETRY_RETENTION_DAYS", "0") or 0)

# This process's identity, used for the single-writer lock below.
WRITER_ID = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"

# A writer that has not refreshed its heartbeat within this many seconds is
# considered dead and its lock can be taken over.
WRITER_LOCK_STALE_SECONDS = 180.0


def minute_key(dt: datetime) -> str:
    """Canonical telemetry timestamp: one slot per wall-clock minute."""
    return dt.strftime("%Y-%m-%d %H:%M:00")

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
            CREATE TABLE IF NOT EXISTS writer_lock (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                owner TEXT NOT NULL,
                heartbeat REAL NOT NULL
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

    _migrate_dedupe_telemetry()


def _migrate_dedupe_telemetry():
    """
    One-time migration: collapse telemetry_history to a single row per
    (minute, inverter) and add a UNIQUE index so it can never double up again.

    Duplicate rows within one minute come from a second backend process polling
    the same hardware; every energy figure is integrated per row, so duplicates
    inflated every daily total by however many writers were running. Read-side
    de-duplication protects the numbers, but the constraint is what makes the
    problem structurally impossible.

    Safe to run repeatedly: it is a no-op once the unique index exists.
    """
    try:
        conn = get_db_connection()
        try:
            already = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_telemetry_unique_min_inv'"
            ).fetchone()
            if already:
                return

            dup_rows = conn.execute("""
                SELECT COUNT(*) - COUNT(DISTINCT substr(timestamp, 1, 16) || '|' || inverter_id)
                FROM telemetry_history
            """).fetchone()[0] or 0
            total_rows = conn.execute("SELECT COUNT(*) FROM telemetry_history").fetchone()[0] or 0
        finally:
            conn.close()

        if dup_rows > 0:
            backup = f"{DB_PATH}.bak-{datetime.now(PKT).strftime('%Y%m%d-%H%M%S')}"
            try:
                shutil.copy2(DB_PATH, backup)
                logger.warning(f"Backed up database to {backup} before de-duplicating telemetry")
            except Exception as e:
                logger.error(f"Could not back up DB before migration, aborting migration: {e}")
                return

        conn = get_db_connection()
        try:
            # Normalise every timestamp to its minute slot, keeping the lowest
            # rowid for each (minute, inverter) pair.
            conn.execute("""
                DELETE FROM telemetry_history
                WHERE id NOT IN (
                    SELECT MIN(id) FROM telemetry_history
                    GROUP BY substr(timestamp, 1, 16), inverter_id
                )
            """)
            conn.execute("""
                UPDATE telemetry_history
                SET timestamp = substr(timestamp, 1, 16) || ':00'
                WHERE substr(timestamp, 18, 2) != '00'
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_telemetry_unique_min_inv
                ON telemetry_history (timestamp, inverter_id)
            """)
            conn.commit()
            logger.warning(
                f"Telemetry de-duplication complete: removed {dup_rows} duplicate rows "
                f"of {total_rows}; UNIQUE(timestamp, inverter_id) now enforced."
            )
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error de-duplicating telemetry history: {e}")


def purge_old_telemetry() -> int:
    """
    Drop 1-minute telemetry older than the configured retention window.

    Disabled by default: telemetry_history grows by roughly 5,800 rows a day,
    which SQLite handles comfortably, and the daily totals the dashboard reports
    are kept separately in daily_totals. Set SOLAR_TELEMETRY_RETENTION_DAYS to
    enable it.
    """
    if TELEMETRY_RETENTION_DAYS <= 0:
        return 0
    try:
        cutoff = (datetime.now(PKT) - timedelta(days=TELEMETRY_RETENTION_DAYS)).strftime("%Y-%m-%d")
        conn = get_db_connection()
        try:
            cur = conn.execute("DELETE FROM telemetry_history WHERE substr(timestamp, 1, 10) < ?", (cutoff,))
            conn.commit()
            if cur.rowcount:
                logger.info(f"Purged {cur.rowcount} telemetry rows older than {cutoff}")
            return cur.rowcount or 0
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error purging old telemetry: {e}")
        return 0


def claim_writer_lock() -> bool:
    """
    Try to become the single telemetry writer for this database.

    Returns True if this process holds the lock. A second backend instance
    pointed at the same solar.db will return False and must not poll hardware
    or log telemetry -- it can still serve read-only API traffic. This is what
    stops two pollers from both writing (and both fighting over the serial
    ports).
    """
    try:
        now_ts = datetime.now(timezone.utc).timestamp()
        conn = get_db_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT owner, heartbeat FROM writer_lock WHERE id = 1").fetchone()

            if row and row["owner"] != WRITER_ID:
                age = now_ts - float(row["heartbeat"] or 0.0)
                if age < WRITER_LOCK_STALE_SECONDS:
                    conn.rollback()
                    return False
                logger.warning(
                    f"Taking over stale telemetry writer lock from {row['owner']} (idle {age:.0f}s)"
                )

            conn.execute("""
                INSERT INTO writer_lock (id, owner, heartbeat) VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET owner=excluded.owner, heartbeat=excluded.heartbeat
            """, (WRITER_ID, now_ts))
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        # If the lock cannot be evaluated, fail open so a single healthy
        # instance never stops recording because of a transient DB error.
        logger.error(f"Error claiming writer lock (continuing as writer): {e}")
        return True


def release_writer_lock():
    """Give up the writer lock so another instance can take over immediately."""
    try:
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM writer_lock WHERE id = 1 AND owner = ?", (WRITER_ID,))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error releasing writer lock: {e}")

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
            # Legacy tables from earlier revisions; dropped so a reset does not
            # leave stale lifetime counters behind. Automations and saved
            # inverter settings are deliberately preserved.
            conn.execute("DROP TABLE IF EXISTS lifetime_totals;")
            conn.execute("DROP TABLE IF EXISTS lifetime_totals_midnight;")
            conn.execute("DROP TABLE IF EXISTS writer_lock;")
            conn.commit()
        finally:
            conn.close()
        init_db()
        logger.info("Database completely nuked and recreated clean.")
        return True
    except Exception as e:
        logger.error(f"Error nuking database: {e}")
        return False
def log_telemetry_snapshot(readings: Dict[str, Dict[str, Any]], bms_power_w: Optional[float] = None):
    """
    Log a 1-minute telemetry snapshot into sqlite telemetry_history table in local Pakistan Time (PKT).
    Format: YYYY-MM-DD HH:MM:SS
    """
    try:
        conn = get_db_connection()
        try:
            now_pkt = datetime.now(PKT)
            # One canonical slot per minute. Combined with the UNIQUE index this
            # makes a duplicate sample overwrite rather than double-count.
            time_str = minute_key(now_pkt)

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
                    ON CONFLICT(timestamp, inverter_id) DO UPDATE SET
                        solar_w=excluded.solar_w,
                        load_w=excluded.load_w,
                        grid_w=excluded.grid_w,
                        battery_w=excluded.battery_w,
                        battery_pct=excluded.battery_pct,
                        battery_v=excluded.battery_v,
                        grid_v=excluded.grid_v,
                        temp_c=excluded.temp_c
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
                ON CONFLICT(timestamp, inverter_id) DO UPDATE SET
                    solar_w=excluded.solar_w,
                    load_w=excluded.load_w,
                    grid_w=excluded.grid_w,
                    battery_w=excluded.battery_w,
                    battery_pct=excluded.battery_pct,
                    battery_v=excluded.battery_v,
                    grid_v=excluded.grid_v,
                    temp_c=excluded.temp_c
            """, (time_str, total_solar, total_load, total_grid, total_bat, avg_soc, avg_bat_v, max_grid_v, avg_temp))

            if bms_power_w is not None:
                conn.execute("""
                    INSERT INTO telemetry_history
                    (timestamp, inverter_id, solar_w, load_w, grid_w, battery_w, battery_pct, battery_v, grid_v, temp_c)
                    VALUES (?, 'bms', 0, 0, 0, ?, ?, ?, 0, ?)
                    ON CONFLICT(timestamp, inverter_id) DO UPDATE SET
                        solar_w=excluded.solar_w,
                        load_w=excluded.load_w,
                        grid_w=excluded.grid_w,
                        battery_w=excluded.battery_w,
                        battery_pct=excluded.battery_pct,
                        battery_v=excluded.battery_v,
                        grid_v=excluded.grid_v,
                        temp_c=excluded.temp_c
                """, (time_str, float(bms_power_w), avg_soc, avg_bat_v, avg_temp))

            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error logging telemetry snapshot: {e}")


def _fetch_samples(conn, date_str: str, inverter_id: str,
                   columns: str = "solar_w, load_w, grid_w, battery_w") -> List[sqlite3.Row]:
    """
    Fetch one telemetry sample per wall-clock minute for a day, oldest first.

    Historical rows written before the UNIQUE(timestamp, inverter_id) migration
    can still contain several samples for the same minute (one per backend
    process that was running). GROUP BY the minute so every minute contributes
    exactly once, whatever is in the table.
    """
    return conn.execute(f"""
        SELECT substr(timestamp, 1, 16) AS minute, {columns}
        FROM telemetry_history
        WHERE timestamp LIKE ? AND inverter_id = ?
        GROUP BY substr(timestamp, 1, 16)
        ORDER BY minute ASC
    """, (f"{date_str}%", inverter_id)).fetchall()


def _sample_durations(rows: List[sqlite3.Row]) -> List[float]:
    """
    Return the number of seconds each sample represents.

    Energy must be integrated against the real spacing between samples, never
    against an assumed one-minute cadence: a backfilled day is spaced 10 minutes
    apart and a restart can leave a gap, so a fixed divisor silently scales the
    whole day's kWh up or down. Each sample covers the interval up to the next
    one, clamped to MAX_GAP_SECONDS so downtime is not extrapolated over.
    """
    n = len(rows)
    if n == 0:
        return []

    stamps: List[Optional[datetime]] = []
    for r in rows:
        try:
            stamps.append(datetime.strptime(r["minute"], "%Y-%m-%d %H:%M"))
        except (ValueError, TypeError):
            stamps.append(None)

    durations: List[Optional[float]] = []
    for i in range(n):
        gap = None
        if stamps[i] is not None:
            for j in range(i + 1, n):
                if stamps[j] is not None:
                    gap = (stamps[j] - stamps[i]).total_seconds()
                    break
        durations.append(min(gap, MAX_GAP_SECONDS) if (gap and gap > 0) else None)

    # The final sample has no successor. Give it the day's typical cadence so a
    # 1-minute day and a 10-minute backfilled day are both handled correctly.
    known = sorted(d for d in durations if d is not None)
    # Lower median: exact for a uniform cadence, and biased to under-count
    # rather than over-count when the spacing is ragged.
    typical = known[(len(known) - 1) // 2] if known else NOMINAL_SAMPLE_SECONDS
    return [d if d is not None else typical for d in durations]


def _integration_coverage(rows: List[sqlite3.Row], date_str: str) -> float:
    """
    Fraction of the day's elapsed minutes that carry a telemetry sample.

    This is what separates "the integration is a complete record" from "the
    backend was down for part of the day, so the integration must under-report".
    """
    if not rows:
        return 0.0
    now_pkt = datetime.now(PKT)
    if date_str == now_pkt.strftime("%Y-%m-%d"):
        elapsed = now_pkt.hour * 60 + now_pkt.minute + 1
    else:
        elapsed = 1440
    return len(rows) / float(max(1, elapsed))


def integrate_samples(rows: List[sqlite3.Row]) -> Dict[str, float]:
    """Integrate power samples (W) into energy (kWh) using real sample spacing."""
    totals = {"solar": 0.0, "load": 0.0, "gridImport": 0.0,
              "gridExport": 0.0, "batteryCharge": 0.0, "batteryDischarge": 0.0}

    for r, secs in zip(rows, _sample_durations(rows)):
        hours = secs / 3600.0
        s_kw = max(0.0, (r["solar_w"] or 0.0) / 1000.0)
        l_kw = max(0.0, (r["load_w"] or 0.0) / 1000.0)
        g_kw = (r["grid_w"] or 0.0) / 1000.0
        b_kw = (r["battery_w"] or 0.0) / 1000.0

        totals["solar"] += s_kw * hours
        totals["load"] += l_kw * hours
        if g_kw > 0:
            totals["gridImport"] += g_kw * hours
        else:
            totals["gridExport"] += abs(g_kw) * hours
        if b_kw > 0:
            totals["batteryCharge"] += b_kw * hours
        else:
            totals["batteryDischarge"] += abs(b_kw) * hours

    return totals


def query_bms_daily_totals(date_str: str) -> Dict[str, float]:
    """
    Calculate total kWh charged and total kWh discharged for a given date
    directly from 1-minute BMS RS485 power readings in SQLite.
    """
    try:
        conn = get_db_connection()
        try:
            rows = _fetch_samples(conn, date_str, "bms", columns="battery_w")
            if not rows:
                rows = _fetch_samples(conn, date_str, "all", columns="battery_w")

            charge_kwh = 0.0
            discharge_kwh = 0.0
            for r, secs in zip(rows, _sample_durations(rows)):
                kw = float(r["battery_w"] or 0.0) / 1000.0
                hours = secs / 3600.0
                if kw > 0:
                    charge_kwh += kw * hours
                elif kw < 0:
                    discharge_kwh += abs(kw) * hours

            return {
                "date": date_str,
                "bms_charge_kwh": round(charge_kwh, 2),
                "bms_discharge_kwh": round(discharge_kwh, 2)
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

            fields = [
                ("solar", "solar_start"),
                ("load", "load_start"),
                ("grid_import", "grid_import_start"),
                ("grid_export", "grid_export_start"),
                ("battery_charge", "battery_charge_start"),
                ("battery_discharge", "battery_discharge_start"),
            ]
            prev_cols = {
                "solar": "solar_kwh", "load": "load_kwh", "grid_import": "grid_import_kwh",
                "grid_export": "grid_export_kwh", "battery_charge": "battery_charge_kwh",
                "battery_discharge": "battery_discharge_kwh",
            }

            for inv_id, r in lifetime_readings.items():
                # A register that failed to read comes back as None or 0.0. It must
                # never be treated as a real value: stored as a start-of-day
                # baseline it makes the day's total equal the whole lifetime
                # counter, and used as a current value it wipes a good total to 0.
                current = {}
                for key, _col in fields:
                    v = r.get(key)
                    try:
                        v = float(v) if v is not None else None
                    except (TypeError, ValueError):
                        v = None
                    current[key] = v if (v is not None and v > 0.0) else None

                if all(v is None for v in current.values()):
                    continue

                base_row = conn.execute(
                    "SELECT * FROM lifetime_baselines WHERE date = ? AND inverter_id = ?",
                    (today_str, inv_id)
                ).fetchone()

                baseline = {}
                for key, col in fields:
                    prev = base_row[col] if base_row is not None else None
                    try:
                        prev = float(prev) if prev is not None else None
                    except (TypeError, ValueError):
                        prev = None
                    # Only ever establish a baseline from a real reading, so a
                    # register that was unreadable at midnight gets its baseline
                    # from the first cycle that does read it.
                    baseline[key] = prev if (prev is not None and prev > 0.0) else current[key]

                conn.execute("""
                    INSERT INTO lifetime_baselines
                    (date, inverter_id, solar_start, load_start, grid_import_start, grid_export_start, battery_charge_start, battery_discharge_start)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(date, inverter_id) DO UPDATE SET
                        solar_start=COALESCE(lifetime_baselines.solar_start, excluded.solar_start),
                        load_start=COALESCE(lifetime_baselines.load_start, excluded.load_start),
                        grid_import_start=COALESCE(lifetime_baselines.grid_import_start, excluded.grid_import_start),
                        grid_export_start=COALESCE(lifetime_baselines.grid_export_start, excluded.grid_export_start),
                        battery_charge_start=COALESCE(lifetime_baselines.battery_charge_start, excluded.battery_charge_start),
                        battery_discharge_start=COALESCE(lifetime_baselines.battery_discharge_start, excluded.battery_discharge_start)
                """, (today_str, inv_id, baseline["solar"], baseline["load"], baseline["grid_import"],
                      baseline["grid_export"], baseline["battery_charge"], baseline["battery_discharge"]))
                conn.commit()

                prev_row = conn.execute("""
                    SELECT solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh,
                           battery_charge_kwh, battery_discharge_kwh
                    FROM daily_totals WHERE date = ? AND inverter_id = ?
                """, (today_str, inv_id)).fetchone()

                daily = {}
                for key, _col in fields:
                    keep = float(prev_row[prev_cols[key]] or 0.0) if prev_row is not None else 0.0
                    curr_v, base_v = current[key], baseline[key]

                    if curr_v is None or base_v is None:
                        # Unreadable this cycle: hold the last good value.
                        daily[key] = keep
                        continue

                    delta = curr_v - base_v
                    if delta < 0.0 or delta > MAX_LIFETIME_DELTA_KWH:
                        logger.warning(
                            f"Implausible lifetime delta for {inv_id}.{key}: "
                            f"{curr_v} - {base_v} = {delta:.1f} kWh. Holding {keep} kWh."
                        )
                        daily[key] = keep
                        continue

                    # Take the delta as-is. Never ratchet with max(keep, ...):
                    # a single high-but-plausible frame would then be latched in
                    # for the rest of the day with no way to recover, which is
                    # how inv1's load total reached 33.5 kWh against a real 19.7.
                    # A failed read is already handled above by holding the
                    # previous value, so nothing here needs protecting from zero.
                    daily[key] = round(delta, 1)

                daily_s = daily["solar"]
                daily_l = daily["load"]
                daily_gi = daily["grid_import"]
                daily_ge = daily["grid_export"]
                daily_bc = daily["battery_charge"]
                daily_bd = daily["battery_discharge"]

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


METRIC_KEYS = ("solar", "load", "gridImport", "gridExport", "batteryCharge", "batteryDischarge")


def get_combined_daily_total(date_str: str, inverter_id: str = "all") -> Dict[str, Any]:
    """
    Daily totals for one date and one inverter selection.

    "all" is the sum of the individually validated inverters rather than a
    separately stored aggregate row. The stored row is written in the same pass
    that computes the per-inverter figures, so a bad reading on one inverter used
    to propagate into it -- and because the whole-plant sanity ceiling is
    necessarily three times looser, a value that was rejected per inverter could
    still pass as a plant total. Summing validated parts also guarantees the
    plant figure equals inv1 + inv2 + inv3, which the stored row did not.
    """
    if inverter_id == "all":
        parts = [_daily_total_for_inverter(date_str, inv) for inv in ("inv1", "inv2", "inv3")]
        if any(any(p[k] > 0.0 for k in METRIC_KEYS) for p in parts):
            sources = {p["source"] for p in parts}
            return {
                "time": date_str,
                "source": sources.pop() if len(sources) == 1 else "mixed",
                **{k: round(sum(p[k] for p in parts), 1) for k in METRIC_KEYS},
            }
        # No per-inverter data at all: fall back to a stored plant row, which is
        # what DESSMonitor backfill writes for older dates.
        return _daily_total_for_inverter(date_str, "all")

    return _daily_total_for_inverter(date_str, inverter_id)


def _daily_total_for_inverter(date_str: str, inverter_id: str) -> Dict[str, Any]:
    """
    Return the daily energy totals for one date and one inverter selection.

    Two independent sources exist for every figure:

      1. The inverter's own lifetime energy registers (QET/QLT/QGT/QFT/QCT/QDT),
         differenced against a start-of-day baseline and stored in daily_totals.
         This is the authoritative source -- it is the same counter the inverter
         display and DESSMonitor report, and it cannot drift.
      2. Integration of the 1-minute power samples in telemetry_history. This is
         a fallback: it misses any period the backend was down and inherits every
         sensor error, so it is only used when the hardware value is unavailable.

    Earlier revisions discarded any hardware value above a 35 kWh/inverter cap
    and fell back to the integration -- but inv1 and inv2 genuinely produce
    39-49 kWh on a clear day, so the correct number was thrown away every good
    day. The caps here exist only to reject corrupt register frames and sit far
    above any physically achievable daily total.
    """
    metrics = METRIC_KEYS
    try:
        conn = get_db_connection()
        try:
            max_daily = MAX_DAILY_KWH_ALL if inverter_id == "all" else MAX_DAILY_KWH_PER_INVERTER

            row = conn.execute("""
                SELECT solar_kwh, load_kwh, grid_import_kwh, grid_export_kwh, battery_charge_kwh, battery_discharge_kwh
                FROM daily_totals
                WHERE date = ? AND inverter_id = ?
            """, (date_str, inverter_id)).fetchone()

            hw = {
                "solar": row["solar_kwh"] if row else 0.0,
                "load": row["load_kwh"] if row else 0.0,
                "gridImport": row["grid_import_kwh"] if row else 0.0,
                "gridExport": row["grid_export_kwh"] if row else 0.0,
                "batteryCharge": row["battery_charge_kwh"] if row else 0.0,
                "batteryDischarge": row["battery_discharge_kwh"] if row else 0.0,
            }
            hw_corrupt = False
            for k in metrics:
                v = float(hw[k] or 0.0)
                if v < 0.0 or v > max_daily:
                    logger.warning(
                        f"Rejecting corrupt hardware total {inverter_id}.{k} for {date_str}: {v} kWh"
                    )
                    v = 0.0
                    hw_corrupt = True
                hw[k] = v

            # Pick one source for the whole day rather than mixing per metric:
            # a metric that is legitimately zero in hardware (no battery
            # discharge today, say) would otherwise fall through to the
            # integration and pick up sensor noise. Never take max() of the two
            # either -- that biases every figure upwards.
            has_hw = any(hw[k] > 0.0 for k in metrics)

            # A register rejected by the absolute ceiling makes the whole row
            # suspect, so the day falls back to the integration rather than
            # reporting a zero for the corrupt metric beside good values.
            if hw_corrupt or not has_hw:
                final = integrate_samples(_fetch_samples(conn, date_str, inverter_id))
                return {"time": date_str, "source": "integrated",
                        **{k: round(final[k], 1) for k in metrics}}

            # Choose between the two sources by how complete the 1-minute record
            # is, not by how far apart they are.
            #
            # Checked against DESSMonitor for 2026-08-22, the integration matched
            # the cloud figures on every metric (inv2 load 59.3 vs 59.4, import
            # 33.2 vs 34.2) while the register-derived totals did not (85.6 and
            # 65.4). QET and QFT track real energy, but the QLT and QGT deltas
            # run well ahead of it, so "hardware is authoritative" does not hold
            # for every register on this equipment.
            #
            # The integration's only real weakness is missing time, and that is
            # directly measurable: when samples cover the day, it is a complete
            # record and is used. When the backend was down for a meaningful part
            # of the day, the lifetime registers are the only source that saw the
            # missing hours, so they are used instead.
            samples = _fetch_samples(conn, date_str, inverter_id)
            coverage = _integration_coverage(samples, date_str)
            integrated = integrate_samples(samples)

            if coverage >= MIN_INTEGRATION_COVERAGE and any(integrated[k] > 0.0 for k in metrics):
                final, source = integrated, "integrated"
            else:
                # Falling back to the registers, but they still have to be
                # credible against whatever the integration did capture. The
                # samples that exist put a floor under the day's real energy,
                # and the time they miss puts a ceiling on how far the registers
                # may exceed them: at most as much again as the uncovered
                # fraction could hold, with margin.
                headroom = (1.0 / coverage if coverage > 0.05 else 20.0) * 1.5
                suspect = [
                    k for k in metrics
                    if integrated[k] > 0.5 and (
                        hw[k] > integrated[k] * headroom or hw[k] < integrated[k] * 0.8
                    )
                ]
                if suspect:
                    logger.warning(
                        f"Hardware totals for {inverter_id} on {date_str} are not credible on "
                        f"{suspect} at {coverage:.0%} telemetry coverage "
                        f"(e.g. {suspect[0]}: hardware {hw[suspect[0]]} vs integrated "
                        f"{integrated[suspect[0]]:.1f} kWh); using the integration."
                    )
                    final, source = integrated, "integrated"
                else:
                    if samples:
                        logger.info(
                            f"Telemetry covers only {coverage:.0%} of {date_str} for {inverter_id}; "
                            f"using the hardware lifetime registers."
                        )
                    final, source = hw, "hardware"

            return {
                "time": date_str,
                "source": source,
                **{k: round(final[k], 1) for k in metrics},
            }
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error computing combined daily total: {e}")
        return {"time": date_str, "source": "error", **{k: 0.0 for k in metrics}}


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
                SELECT MIN(timestamp) AS timestamp, battery_pct
                FROM telemetry_history
                WHERE timestamp LIKE ? AND inverter_id = 'all'
                GROUP BY substr(timestamp, 1, 16)
                ORDER BY timestamp ASC
            """, (f"{date_str}%",)).fetchall()
            for br in bms_rows:
                ts_str = br["timestamp"]
                t_key = ts_str[11:16] if len(ts_str) >= 16 else ts_str
                if br["battery_pct"] and br["battery_pct"] > 0:
                    bms_soc_map[t_key] = br["battery_pct"]

            # One point per minute: pre-migration days can hold several samples
            # per minute, which would otherwise plot as a vertical smear.
            rows = conn.execute("""
                SELECT MIN(timestamp) AS timestamp, solar_w, load_w, grid_w, battery_w, battery_pct, grid_v
                FROM telemetry_history
                WHERE timestamp LIKE ? AND inverter_id = ?
                GROUP BY substr(timestamp, 1, 16)
                ORDER BY timestamp ASC
            """, (f"{date_str}%", inverter_id)).fetchall()

            results = []
            last_known_graph_soc = None

            for r in rows:
                ts_str = r["timestamp"]  # "YYYY-MM-DD HH:MM:SS"
                time_label = ts_str[11:16] if len(ts_str) >= 16 else ts_str

                solar_kw = round(r["solar_w"] / 1000.0, 2)
                load_kw = round(r["load_w"] / 1000.0, 2)
                grid_kw = round(r["grid_w"] / 1000.0, 2)
                bat_kw = round(r["battery_w"] / 1000.0, 2)

                # STRICT: Use Knox BMS RS485 SOC ONLY (never fall back to inverter wire SOC!)
                if time_label in bms_soc_map:
                    last_known_graph_soc = bms_soc_map[time_label]

                raw_soc = last_known_graph_soc if last_known_graph_soc is not None else 0.0

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
def query_cumulative_history(date_str: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
    """
    Build the intraday cumulative energy curve for one day.

    Energy is accumulated from the 1-minute power samples using their real
    spacing, so the final point of the curve agrees with the day's integrated
    total instead of scaling with however many samples happen to exist.
    """
    metrics = ("solar", "load", "gridImport", "gridExport", "batteryCharge", "batteryDischarge")
    try:
        conn = get_db_connection()
        try:
            rows = _fetch_samples(
                conn, date_str, inverter_id,
                columns="solar_w, load_w, grid_w, battery_w, battery_pct"
            )

            if rows:
                results = [{
                    "time": "00:00",
                    **{k: 0.0 for k in metrics},
                    "batteryLevel": rows[0]["battery_pct"] or 0.0
                }]

                cum = {k: 0.0 for k in metrics}
                for r, secs in zip(rows, _sample_durations(rows)):
                    hours = secs / 3600.0
                    s_kw = max(0.0, (r["solar_w"] or 0.0) / 1000.0)
                    l_kw = max(0.0, (r["load_w"] or 0.0) / 1000.0)
                    g_kw = (r["grid_w"] or 0.0) / 1000.0
                    b_kw = (r["battery_w"] or 0.0) / 1000.0

                    cum["solar"] += s_kw * hours
                    cum["load"] += l_kw * hours
                    if g_kw > 0:
                        cum["gridImport"] += g_kw * hours
                    else:
                        cum["gridExport"] += abs(g_kw) * hours
                    if b_kw > 0:
                        cum["batteryCharge"] += b_kw * hours
                    else:
                        cum["batteryDischarge"] += abs(b_kw) * hours

                    minute = r["minute"] or ""
                    time_label = minute[11:16] if len(minute) >= 16 else minute
                    if time_label and time_label != "00:00":
                        results.append({
                            "time": time_label,
                            **{k: round(cum[k], 2) for k in metrics},
                            "batteryLevel": r["battery_pct"] or 0.0
                        })
                return results

            # No power samples for this day: fall back to a smooth ramp up to the
            # day's known total so the chart is not simply blank.
            day_tot = query_daily_totals_for_day(date_str, inverter_id) or {}
            totals = {k: float(day_tot.get(k, 0.0) or 0.0) for k in metrics}
            if not any(totals.values()):
                return []

            now_pkt = datetime.now(PKT)
            today_str = now_pkt.strftime("%Y-%m-%d")
            if date_str == today_str:
                max_minutes = now_pkt.hour * 60 + now_pkt.minute + 1
            else:
                max_minutes = 1440

            results = []
            for m in range(0, max_minutes, 10):
                time_label = f"{m // 60:02d}:{m % 60:02d}"
                frac = min(1.0, m / max(1, max_minutes - 10))
                results.append({
                    "time": time_label,
                    **{k: round(totals[k] * frac, 2) for k in metrics},
                    "batteryLevel": 0.0
                })
            return results
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error querying cumulative history: {e}")
        return []
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
                    actions=excluded.actions,
                    -- Rescheduling clears the "already ran today" stamp so a
                    -- time moved later in the same day still fires.
                    last_triggered=CASE WHEN automations.time_of_day != excluded.time_of_day
                                        THEN NULL ELSE automations.last_triggered END
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
            # Match every automation whose time has come and which has not run
            # today, rather than only those matching the current minute exactly.
            # A polling cycle can overrun a minute (serial reads are slow), and
            # an exact match silently skipped the automation for the whole day.
            rows = conn.execute("""
                SELECT id, name, time_of_day, inverter_id, actions, last_triggered
                FROM automations
                WHERE enabled = 1
                  AND time_of_day <= ?
                  AND (last_triggered IS NULL OR substr(last_triggered, 1, 10) != ?)
            """, (current_time_hhmm, current_date_str)).fetchall()

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

            return due
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error getting due automations: {e}")
        return []


def mark_automation_triggered(auto_id: str, current_date_str: str, current_time_hhmm: str):
    """
    Record that an automation ran. Called only after its commands were actually
    delivered, so a failed serial write is retried on the next cycle instead of
    being silently swallowed for the rest of the day.
    """
    try:
        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE automations SET last_triggered = ? WHERE id = ?",
                (f"{current_date_str} {current_time_hhmm}", auto_id)
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error stamping automation {auto_id} as triggered: {e}")