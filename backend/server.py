import os
import time
import threading
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

import db
from dess_scraper import dess_scraper
from serial_reader import serial_reader, INVERTERS_CONFIG
from battery_bms import bms, start_bms_poller

serial_reader_instance = serial_reader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SOLAR_SERVER")

app = FastAPI(title="Solar Dashboard Backend Server", version="2.0")

last_api_access_time = 0

# CORS middleware for local & network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background 1-minute telemetry logger thread
def background_telemetry_loop():
    global last_api_access_time
    logger.info("Starting background dynamic telemetry logging thread...")
    last_dess_poll_time = 0
    last_db_log_time = 0

    while True:
        try:
            now_sec = time.time()
            user_connected = (now_sec - last_api_access_time) < 10
            
            import battery_bms
            battery_bms.fast_poll_active = user_connected

            if user_connected or (now_sec - last_db_log_time >= 60):
                # 1. Capture RS232 telemetry snapshot from local USB inverters
                readings = serial_reader_instance.poll_all_inverters()
                if readings:
                    # Override glitchy inverter SOC and voltage with reliable RS485 BMS data
                    bms_data = bms.get_latest_data()
                    bms_soc = float(bms_data.get("soc", 0.0))
                    bms_v = float(bms_data.get("voltage", 0.0))
                    if 0.0 <= bms_soc <= 100.0 and bms_soc > 0:
                        for inv_id in readings:
                            readings[inv_id]["battery_capacity_pct"] = bms_soc
                            if 35.0 <= bms_v <= 70.0:
                                readings[inv_id]["battery_voltage"] = bms_v

                now_sec = time.time()
                # Log to SQLite only once every 60 seconds to prevent DB bloat
                if now_sec - last_db_log_time >= 60:
                    last_db_log_time = now_sec
                    db.log_telemetry_snapshot(readings)

            # 2. Automatically poll hardware lifetime totals and calculate daily values
            now_dt = datetime.now()
            if now_dt.second >= 50 and (now_sec - last_dess_poll_time > 40):
                last_dess_poll_time = now_sec
                hw_totals_map = serial_reader_instance.poll_daily_totals()
                if hw_totals_map:
                    db.update_lifetime_totals_and_calculate_daily(hw_totals_map)
                    logger.info("Updated hardware lifetime-based daily totals in SQLite")

            # 3. Check for due automations (timers) every minute
            now_pkt = datetime.now(db.PKT)
            time_hhmm = now_pkt.strftime("%H:%M")
            date_str = now_pkt.strftime("%Y-%m-%d")

            due_automations = db.get_due_automations(time_hhmm, date_str)
            if due_automations:
                for auto in due_automations:
                    logger.info(f"Triggering scheduled automation '{auto['name']}' ({auto['id']}) for inverter '{auto['inverter_id']}'")
                    for action in auto.get("actions", []):
                        cmd = action.get("command")
                        if cmd:
                            target_inv = auto.get("inverter_id", "all")
                            if target_inv == "all":
                                for inv_k in ["inv1", "inv2", "inv3"]:
                                    res = serial_reader_instance.send_command(inv_k, cmd)
                                    logger.info(f"Executed automation command {cmd} on {inv_k}: {res}")
                            else:
                                res = serial_reader_instance.send_command(target_inv, cmd)
                                logger.info(f"Executed automation command {cmd} on {target_inv}: {res}")

        except Exception as e:
            logger.error(f"Error in background telemetry loop: {e}")
        time.sleep(1)

# Start background thread on server startup
@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=background_telemetry_loop, daemon=True)
    t.start()
    start_bms_poller()

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
def get_battery():
    """
    Returns the real-time battery status straight from the BMS via RS485,
    enriched with current and temperature from the inverter telemetry since the 
    Knox BMS RS485 has a fixed payload omitting those fields.
    """
    data = bms.get_latest_data()
    
    try:
        # Fallback to inverter aggregate telemetry for current and temperature
        readings = serial_reader_instance.readings_cache
        if readings:
            total_charge = sum(r.get("battery_charge_current", 0.0) for r in readings.values() if "battery_charge_current" in r)
            total_discharge = sum(r.get("battery_discharge_current", 0.0) for r in readings.values() if "battery_discharge_current" in r)
            
            net_current = total_charge - total_discharge
            data["current"] = net_current
            data["power"] = round(data["voltage"] * net_current, 2)
            
            if net_current > 0.5:
                data["state"] = "Charging"
            elif net_current < -0.5:
                data["state"] = "Discharging"
            else:
                data["state"] = "Idle"
            
            temps = [r.get("inverter_temp_c", 0.0) for r in readings.values() if "inverter_temp_c" in r]
            if temps:
                data["temperature"] = round(sum(temps) / len(temps), 1)
    except Exception as e:
        logger.error(f"Error enriching BMS data: {e}")
        
    return data

@app.get("/api/telemetry")
def get_telemetry(inverter: str = Query("all")):
    global last_api_access_time
    last_api_access_time = time.time()
    return serial_reader_instance.get_telemetry_for_selection(inverter)

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

@app.post("/api/backfill")
@app.get("/api/backfill")
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

@app.get("/api/restart_container")
@app.post("/api/restart_container")
def restart_container():
    """
    Exits the process so Docker's restart: unless-stopped policy restarts the container
    and loads the latest updated Python files from disk.
    """
    def _do_exit():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=_do_exit).start()
    return {"status": "restarting", "message": "Backend container restarting..."}

@app.get("/api/nuke_db")
@app.get("/api/reset_db")
@app.post("/api/reset_db")
def reset_database():
    """
    Purge all old telemetry history and daily totals from SQLite DB.
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

@app.post("/api/inverter_settings/update")
def update_inverter_setting(payload: Dict[str, Any]):
    """
    Update Inverter Setting by sending command (e.g. POP01, PCP02, PEb, PDb).
    Payload: {"inverter": "inv3", "command": "POP01"}
    """
    try:
        inv_id = payload.get("inverter", "inv3")
        cmd = payload.get("command")
        if not cmd:
            raise HTTPException(status_code=400, detail="Missing command parameter")
        
        res = serial_reader_instance.set_inverter_setting(inv_id, cmd)
        return res
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

@app.post("/api/automations")
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

@app.put("/api/automations/{auto_id}")
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

@app.delete("/api/automations/{auto_id}")
def delete_automation_endpoint(auto_id: str):
    """Delete an automation."""
    try:
        ok = db.delete_automation(auto_id)
        return {"success": ok}
    except Exception as e:
        logger.error(f"Error deleting automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/automations/{auto_id}/toggle")
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
