import os
import re
import time
import threading
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks, Header, Depends
from fastapi.middleware.cors import CORSMiddleware

import db
from dess_scraper import dess_scraper
from serial_reader import serial_reader, INVERTERS_CONFIG
from battery_bms import bms, start_bms_poller

serial_reader_instance = serial_reader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SOLAR_SERVER")

last_api_access_time = 0

# --- Access control -----------------------------------------------------------
#
# This backend is reachable from the public internet, and its write endpoints
# reconfigure real inverter hardware. Set SOLAR_API_TOKEN to require a matching
# X-Solar-Token header on every mutating request. If it is unset the server
# still runs (so an existing deployment keeps working) but logs a warning at
# startup, and the read-only endpoints are unaffected either way.
API_TOKEN = os.getenv("SOLAR_API_TOKEN", "").strip()

# Comma-separated list of allowed browser origins, or "*".
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("SOLAR_ALLOWED_ORIGINS", "*").split(",") if o.strip()]


def require_token(x_solar_token: Optional[str] = Header(default=None)):
    """Dependency guarding every endpoint that changes state."""
    if not API_TOKEN:
        return
    if x_solar_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Solar-Token")


# --- Inverter command allow-list ----------------------------------------------
#
# Commands were previously passed through to the serial port verbatim, so any
# page in the user's browser could send arbitrary Voltronic commands. Only the
# settings the UI actually exposes are accepted, and voltage setpoints must fall
# within ranges that are safe for a 48 V LiFePO4 bank.
ALLOWED_COMMANDS = {
    # Output source priority
    "POP00", "POP01", "POP02",
    # Charger source priority
    "PCP01", "PCP02", "PCP03",
    # Feed-to-grid enable / disable
    "PEd", "PDd",
}

# prefix -> (min volts, max volts)
ALLOWED_VOLTAGE_COMMANDS = {
    "PBCV": (44.0, 54.0),   # back-to-grid voltage
    "PBDV": (48.0, 58.0),   # back-to-discharge voltage
    "PSDV": (40.0, 48.0),   # low-battery cut-off voltage
    "PCVV": (48.0, 58.4),   # bulk / absorption charging voltage
    "PBFT": (48.0, 58.4),   # float charging voltage
}

_VOLTAGE_CMD_RE = re.compile(r"^(" + "|".join(ALLOWED_VOLTAGE_COMMANDS) + r")(\d{2}\.\d)$")


def validate_inverter_command(cmd: str) -> str:
    """Return the command if it is permitted, otherwise raise HTTP 400."""
    cmd = (cmd or "").strip()
    if cmd in ALLOWED_COMMANDS:
        return cmd

    m = _VOLTAGE_CMD_RE.match(cmd)
    if m:
        prefix, value = m.group(1), float(m.group(2))
        low, high = ALLOWED_VOLTAGE_COMMANDS[prefix]
        if low <= value <= high:
            return cmd
        raise HTTPException(
            status_code=400,
            detail=f"{prefix} value {value}V is outside the safe range {low}-{high}V",
        )

    raise HTTPException(status_code=400, detail=f"Command '{cmd}' is not permitted")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not API_TOKEN:
        logger.warning(
            "SOLAR_API_TOKEN is not set: write endpoints are unauthenticated. "
            "Set it in docker-compose.yml and in the dashboard's Backend settings."
        )
    threading.Thread(target=background_telemetry_loop, daemon=True, name="telemetry").start()
    start_bms_poller()
    try:
        yield
    finally:
        db.release_writer_lock()


app = FastAPI(title="Solar Dashboard Backend Server", version="2.1", lifespan=lifespan)

# CORS for local & network access. Credentials are disabled: the API uses no
# cookies, and "*" combined with allow_credentials causes Starlette to reflect
# any origin back as trusted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background 1-minute telemetry logger thread
# Set once the writer lock has been lost, so the warning is logged only once.
_writer_warned = False


def background_telemetry_loop():
    logger.info("Starting background 1-minute telemetry logging thread...")
    global _writer_warned
    last_dess_poll_time = 0.0
    last_db_log_time = 0.0
    last_lock_refresh = 0.0
    last_purge_time = time.time()
    last_automation_check = 0.0
    is_writer = False

    while True:
        try:
            now_sec = time.time()

            # Exactly one process may poll the hardware and write telemetry.
            # Two backend instances sharing solar.db each wrote their own sample
            # every minute, and because energy is integrated per sample that
            # doubled every daily total. Re-check periodically so this instance
            # takes over automatically if the current writer dies.
            if now_sec - last_lock_refresh >= 30:
                last_lock_refresh = now_sec
                is_writer = db.claim_writer_lock()
                if not is_writer and not _writer_warned:
                    _writer_warned = True
                    logger.warning(
                        "Another backend instance already owns the telemetry writer lock. "
                        "This instance will serve the API read-only and will not poll hardware."
                    )
                elif is_writer and _writer_warned:
                    _writer_warned = False
                    logger.info("Acquired the telemetry writer lock; resuming hardware polling.")

            if not is_writer:
                time.sleep(1)
                continue

            user_connected = (now_sec - last_api_access_time) < 10

            import battery_bms
            battery_bms.fast_poll_active = user_connected

            # Poll the inverters continuously while someone is watching the
            # dashboard so the live view stays responsive, but persist a sample
            # only once a minute.
            if user_connected or (now_sec - last_db_log_time >= 60):
                due_to_log = (now_sec - last_db_log_time) >= 60
                if due_to_log:
                    # Refresh the BMS immediately before persisting so the stored
                    # SOC matches the stored inverter sample.
                    bms.poll_battery()
                bms_data = bms.get_latest_data()
                bms_soc = float(bms_data.get("soc", 0.0))
                bms_v = float(bms_data.get("voltage", 0.0))
                bms_power_w = float(bms_data.get("power", 0.0))
                if bms_data.get("state") == "Discharging":
                    bms_power_w = -abs(bms_power_w)

                # Capture RS232 telemetry snapshot from local USB inverters
                readings = serial_reader_instance.poll_all_inverters()

                if readings:
                    for inv_id in readings:
                        if 0.0 < bms_soc <= 100.0:
                            readings[inv_id]["battery_capacity_pct"] = bms_soc
                        if 35.0 <= bms_v <= 70.0:
                            readings[inv_id]["battery_voltage"] = bms_v

                if due_to_log:
                    last_db_log_time = time.time()
                    db.log_telemetry_snapshot(readings, bms_power_w)

            # 2. Automatically poll hardware lifetime totals and calculate daily values
            now_dt = datetime.now()
            if now_dt.second >= 50 and (time.time() - last_dess_poll_time > 40):
                last_dess_poll_time = time.time()
                hw_totals_map = serial_reader_instance.poll_daily_totals()
                if hw_totals_map:
                    db.update_lifetime_totals_and_calculate_daily(hw_totals_map)
                    logger.info("Updated hardware lifetime-based daily totals in SQLite")

            # 3. Check for due automations (timers). Every 15s is plenty: due
            #    automations are matched by "time has passed and has not run
            #    today", not by an exact minute, so nothing is missed.
            if time.time() - last_automation_check >= 15:
                last_automation_check = time.time()
                run_due_automations()

            # 4. Apply the telemetry retention window once a day (no-op unless
            #    SOLAR_TELEMETRY_RETENTION_DAYS is set).
            if time.time() - last_purge_time > 86400:
                last_purge_time = time.time()
                db.purge_old_telemetry()

        except Exception as e:
            logger.error(f"Error in background telemetry loop: {e}")
        time.sleep(1)


def run_due_automations():
    """
    Fire any automation whose scheduled time has passed today.

    A polling cycle can take longer than a minute (serial reads are slow), so
    matching only the current HH:MM silently skipped automations. An automation
    is stamped as run only once its commands have actually been delivered, so a
    failed serial write is retried on the next cycle instead of being lost for
    the rest of the day.
    """
    now_pkt = datetime.now(db.PKT)
    time_hhmm = now_pkt.strftime("%H:%M")
    date_str = now_pkt.strftime("%Y-%m-%d")

    for auto in db.get_due_automations(time_hhmm, date_str):
        logger.info(
            f"Triggering scheduled automation '{auto['name']}' ({auto['id']}) "
            f"for inverter '{auto['inverter_id']}'"
        )
        target_inv = auto.get("inverter_id", "all")
        targets = ["inv1", "inv2", "inv3"] if target_inv == "all" else [target_inv]

        delivered = False
        failed = False
        for action in auto.get("actions", []):
            cmd = action.get("command")
            if not cmd:
                continue
            try:
                cmd = validate_inverter_command(cmd)
            except HTTPException as e:
                logger.error(f"Automation '{auto['name']}' has a rejected command {cmd!r}: {e.detail}")
                continue
            for inv_k in targets:
                res = serial_reader_instance.send_command(inv_k, cmd)
                logger.info(f"Executed automation command {cmd} on {inv_k}: {res}")
                if res.get("success"):
                    delivered = True
                else:
                    failed = True

        if delivered and not failed:
            db.mark_automation_triggered(auto["id"], date_str, auto.get("time_of_day", time_hhmm))
        elif not delivered:
            logger.warning(
                f"Automation '{auto['name']}' delivered no commands; will retry on the next cycle"
            )
        else:
            logger.warning(
                f"Automation '{auto['name']}' only partly delivered; will retry on the next cycle"
            )



@app.get("/")
def read_root():
    readings = serial_reader_instance.get_readings()
    return {
        "status": "online",
        "service": "Solar Dashboard RS232 USB Backend",
        "mapped_inverters_count": len(readings),
        "serial_connected": serial_reader_instance.is_connected,
        "is_simulated": getattr(serial_reader_instance, 'is_simulated', False)
    }

@app.get("/api/battery")
def get_battery(date: Optional[str] = Query(None)):
    """
    Returns real-time battery status strictly from Battery BMS RS485,
    along with daily charge/discharge totals calculated from BMS RS485.
    """
    data = bms.get_latest_data()

    # Calculate BMS battery power directly: P_bms = V_bms * I_bms
    bms_v = float(data.get("voltage", 0.0))
    bms_i = float(data.get("current", 0.0))
    bms_power = round(bms_v * bms_i, 2)
    data["power"] = bms_power

    if bms_i > 0.5:
        data["state"] = "Charging"
    elif bms_i < -0.5:
        data["state"] = "Discharging"
    else:
        data["state"] = "Idle"

    target_date = date or datetime.now(db.PKT).strftime("%Y-%m-%d")
    bms_totals = db.query_bms_daily_totals(target_date)
    data["bms_charge_kwh"] = bms_totals["bms_charge_kwh"]
    data["bms_discharge_kwh"] = bms_totals["bms_discharge_kwh"]

    try:
        readings = serial_reader_instance.readings_cache
        if readings:
            temps = [r.get("inverter_temp_c", 0.0) for r in readings.values() if r.get("inverter_temp_c", 0.0) > 0]
            if temps:
                data["temperature"] = round(sum(temps) / len(temps), 1)
    except Exception as e:
        logger.error(f"Error getting temp for BMS data: {e}")

    return data

@app.get("/api/bms_totals")
def get_bms_totals(date: Optional[str] = Query(None)):
    target_date = date or datetime.now(db.PKT).strftime("%Y-%m-%d")
    return db.query_bms_daily_totals(target_date)

@app.get("/api/telemetry")
def get_telemetry(inverter: str = Query("all")):
    global last_api_access_time
    last_api_access_time = time.time()
    telemetry_data = serial_reader_instance.get_telemetry_for_selection(inverter)

    # Strictly override SOC and Battery Voltage using Battery BMS RS485 data ONLY
    try:
        bms_data = bms.get_latest_data()
        bms_soc = bms_data.get("soc", 0)
        bms_v = bms_data.get("voltage", 0.0)
        if bms_soc > 0:
            telemetry_data["battery_capacity_pct"] = int(bms_soc)
        if bms_v > 0:
            telemetry_data["battery_voltage"] = float(bms_v)
    except Exception as e:
        logger.error(f"Error overriding telemetry SOC with BMS RS485: {e}")

    return telemetry_data

@app.get("/api/history")
def get_history(
    date: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    inverter: str = Query("all", description="Filter by 'all', 'inv1', 'inv2', or 'inv3'")
):
    target_date = date or datetime.now(db.PKT).strftime("%Y-%m-%d")
    history_records = db.query_daily_history(target_date, inverter)
    return {
        "date": target_date,
        "inverter": inverter,
        "count": len(history_records),
        "records": history_records
    }

@app.get("/api/cumulative")
def get_cumulative(
    date: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    inverter: str = Query("all", description="Filter by 'all', 'inv1', 'inv2', or 'inv3'")
):
    """
    Cumulative Intraday Graph Endpoint.
    Queries 10-minute cumulative energy totals directly from local SQLite DB.
    """
    target_date = date or datetime.now(db.PKT).strftime("%Y-%m-%d")
    records = db.query_cumulative_history(target_date, inverter)
    return {
        "date": target_date,
        "inverter": inverter,
        "count": len(records),
        "records": records
    }

@app.get("/api/dess_totals")
def get_dess_totals(
    date: Optional[str] = Query(None, description="Format YYYY-MM-DD"),
    month: Optional[str] = Query(None, description="Format YYYY-MM"),
    year: Optional[str] = Query(None, description="Format YYYY"),
    inverter: str = Query("all", description="Filter by 'all', 'inv1', 'inv2', or 'inv3'")
):
    """
    DESS Daily Totals Endpoint.
    Strictly reads from local SQLite database table daily_totals.
    Never auto-scrapes past months unless explicitly backfilled by user.
    """
    try:
        # 1. Single Day Query
        if date:
            tot = db.query_daily_totals_for_day(date, inverter)
            return {
                "date": date,
                "inverter": inverter,
                "totals": tot or {
                    "time": date, "solar": 0.0, "load": 0.0, "gridImport": 0.0, "gridExport": 0.0, "batteryCharge": 0.0, "batteryDischarge": 0.0
                }
            }

        # 2. Monthly View Query (daily totals for a month from SQLite)
        if month:
            totals = db.query_daily_totals_for_month(month, inverter)
            return {
                "month": month,
                "inverter": inverter,
                "count": len(totals),
                "totals": totals
            }

        # 3. Yearly View Query (monthly aggregated totals from SQLite)
        if year:
            totals = db.query_daily_totals_for_year(year, inverter)
            return {
                "year": year,
                "inverter": inverter,
                "count": len(totals),
                "totals": totals
            }

        # Fallback to current month
        curr_month = datetime.now(db.PKT).strftime("%Y-%m")
        totals = db.query_daily_totals_for_month(curr_month, inverter)
        return {"month": curr_month, "inverter": inverter, "count": len(totals), "totals": totals}

    except Exception as e:
        logger.error(f"Error fetching DESS totals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backfill", dependencies=[Depends(require_token)])
def trigger_backfill(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    inverter: str = Query("all")
):
    """
    Explicit Backfill Endpoint: Scrapes historical daily totals from DESSMonitor and saves to SQLite DB.
    Iterates through ALL months between start_date and end_date.
    """
    try:
        now = datetime.now(db.PKT)

        # Build complete list of months between start_date and end_date
        if start_date and end_date:
            months_to_scrape = []
            start_dt = datetime.strptime(start_date[:7], "%Y-%m")
            end_dt = datetime.strptime(end_date[:7], "%Y-%m")
            curr = start_dt
            while curr <= end_dt:
                months_to_scrape.append(curr.strftime("%Y-%m"))
                # Advance to next month
                if curr.month == 12:
                    curr = curr.replace(year=curr.year + 1, month=1)
                else:
                    curr = curr.replace(month=curr.month + 1)
        else:
            months_to_scrape = [now.strftime("%Y-%m")]

        scraped_count = 0
        scraped_months = []

        target_inverters = ["all", "inv1", "inv2", "inv3"] if inverter == "all" else [inverter]

        for inv_id in target_inverters:
            for m_str in months_to_scrape:
                records = dess_scraper.fetch_daily_totals_for_month(m_str, inv_id)
                if records:
                    db.save_daily_totals(records, inv_id)
                    scraped_count += len(records)
                    if m_str not in scraped_months:
                        scraped_months.append(m_str)

        return {
            "status": "success",
            "message": f"Backfilled {scraped_count} daily total records into SQLite DB across {len(scraped_months)}/{len(months_to_scrape)} months.",
            "total_records": scraped_count,
            "months_scraped": scraped_months
        }
    except Exception as e:
        logger.error(f"Error during backfill: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/restart_container", dependencies=[Depends(require_token)])
def restart_container():
    """
    Exit the process so Docker's restart: unless-stopped policy restarts the
    container and picks up updated Python files from disk.

    POST only: as a GET this was reachable from a plain link or an image tag on
    any page the user happened to open.
    """
    def _do_exit():
        time.sleep(0.5)
        # Hand the writer lock over immediately so the replacement process does
        # not have to wait for the stale-lock timeout before it starts logging.
        db.release_writer_lock()
        os._exit(0)
    threading.Thread(target=_do_exit).start()
    return {"status": "restarting", "message": "Backend container restarting..."}

@app.post("/api/reset_db", dependencies=[Depends(require_token)])
def reset_database():
    """
    Purge all telemetry history and daily totals from the SQLite DB.

    POST only, and authenticated when a token is configured. The old GET aliases
    (/api/nuke_db, /api/reset_db) meant a browser prefetch or a stray link could
    destroy the entire history.
    """
    try:
        db.nuke_db()
        return {"status": "success", "message": "Telemetry database and daily totals completely nuked and reset."}
    except Exception as e:
        logger.error(f"Error purging database: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/inverter_settings")
def get_inverter_settings(inverter: str = Query("inv3")):
    """
    Query current Inverter Settings:
    1. Output source priority (POP)
    2. Feed to grid (Grid export enable/disable PEb/PDb)
    3. Charging source priority (PCP)
    """
    try:
        settings = serial_reader_instance.get_inverter_settings(inverter)
        return settings
    except Exception as e:
        logger.error(f"Error querying inverter settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/inverter_settings/update", dependencies=[Depends(require_token)])
def update_inverter_setting(payload: Dict[str, Any]):
    """
    Apply an inverter setting (e.g. POP01, PCP02, PEd, PDd, PBCV52.0).
    Payload: {"inverter": "inv3", "command": "POP01"}

    The command is checked against an allow-list before it reaches the serial
    port; voltage setpoints must also fall inside a safe range. Previously any
    string was written to the hardware verbatim.
    """
    try:
        inv_id = payload.get("inverter", "inv3")
        if inv_id not in {c["id"] for c in INVERTERS_CONFIG}:
            raise HTTPException(status_code=400, detail=f"Unknown inverter '{inv_id}'")

        cmd = payload.get("command")
        if not cmd:
            raise HTTPException(status_code=400, detail="Missing command parameter")
        cmd = validate_inverter_command(cmd)

        return serial_reader_instance.set_inverter_setting(inv_id, cmd)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating inverter setting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/devices")
def get_devices():
    device_map = getattr(serial_reader_instance, 'device_map', {})
    return {
        "registered_inverters": INVERTERS_CONFIG,
        "mapped_devices_count": len(device_map),
        "mapped_devices": [
            {"id": inv_id, "path": path}
            for inv_id, path in device_map.items()
        ],
        "active_device_connected": getattr(serial_reader_instance, 'is_connected', True)
    }

# --- AUTOMATIONS & TIMERS API ENDPOINTS ---

@app.get("/api/automations")
def get_automations():
    """List all configured automations."""
    try:
        autos = db.query_automations()
        return {"automations": autos}
    except Exception as e:
        logger.error(f"Error fetching automations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/automations", dependencies=[Depends(require_token)])
def create_automation(payload: Dict[str, Any]):
    """Create a new automation."""
    try:
        saved = db.save_automation(payload)
        if saved:
            return {"success": True, "automation": saved}
        raise HTTPException(status_code=400, detail="Failed to save automation")
    except Exception as e:
        logger.error(f"Error creating automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/automations/{auto_id}", dependencies=[Depends(require_token)])
def update_automation(auto_id: str, payload: Dict[str, Any]):
    """Update an existing automation."""
    try:
        payload["id"] = auto_id
        saved = db.save_automation(payload)
        if saved:
            return {"success": True, "automation": saved}
        raise HTTPException(status_code=400, detail="Failed to update automation")
    except Exception as e:
        logger.error(f"Error updating automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/automations/{auto_id}", dependencies=[Depends(require_token)])
def delete_automation_endpoint(auto_id: str):
    """Delete an automation."""
    try:
        ok = db.delete_automation(auto_id)
        return {"success": ok}
    except Exception as e:
        logger.error(f"Error deleting automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/automations/{auto_id}/toggle", dependencies=[Depends(require_token)])
def toggle_automation_endpoint(auto_id: str):
    """Toggle automation enabled/disabled status."""
    try:
        new_state = db.toggle_automation(auto_id)
        if new_state is not None:
            return {"success": True, "enabled": new_state}
        raise HTTPException(status_code=404, detail="Automation not found")
    except Exception as e:
        logger.error(f"Error toggling automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Solar Dashboard Backend Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
