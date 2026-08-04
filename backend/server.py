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
from hid_reader import HIDInverterReader, INVERTERS_CONFIG
from battery_bms import bms, start_bms_poller

hid_reader = HIDInverterReader()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SOLAR_SERVER")

app = FastAPI(title="Solar Dashboard Backend Server", version="2.0")

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
    logger.info("Starting background 1-minute telemetry logging thread...")
    last_dess_poll_time = 0

    while True:
        try:
            # 1. Capture HID readings snapshot from local USB inverters
            readings = hid_reader.poll_all_inverters()
            if readings:
                # Override glitchy inverter SOC with reliable RS485 BMS SOC
                bms_data = bms.get_latest_data()
                bms_soc = bms_data.get("soc", 0.0)
                if bms_soc > 0:
                    for inv_id in readings:
                        readings[inv_id]["battery_capacity_pct"] = float(bms_soc)

                db.log_telemetry_snapshot(readings)

            # 2. Every 10 minutes (600 seconds), update daily totals & 10-minute cumulative snapshots directly from local wire telemetry!
            now_sec = time.time()
            if now_sec - last_dess_poll_time >= 600:
                last_dess_poll_time = now_sec
                db.update_daily_totals_from_wire()
                logger.info("Auto-updated current day daily totals & 10-min cumulative snapshots directly from local wire readings")

        except Exception as e:
            logger.error(f"Error in background telemetry loop: {e}")
        time.sleep(10)

# Start background thread on server startup
@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=background_telemetry_loop, daemon=True)
    t.start()
    start_bms_poller()

@app.get("/")
def read_root():
    readings = hid_reader.poll_all_inverters()
    return {
        "status": "online",
        "service": "Solar Dashboard HID USB & DESS Backend",
        "mapped_inverters_count": len(readings),
        "hid_connected": hid_reader.is_connected,
        "is_simulated": getattr(hid_reader, 'is_simulated', False)
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
        readings = hid_reader.readings_cache
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
    return hid_reader.get_telemetry_for_selection(inverter)

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
    Queries 10-minute cumulative energy totals directly from DESSMonitor API.
    Enforces strictly monotonic increase (values only go UP or stay flat).
    """
    target_date = date or datetime.now(db.PKT).strftime("%Y-%m-%d")
    records = dess_scraper.fetch_cumulative_intraday_for_day(target_date, inverter)
    if not records:
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

@app.get("/api/devices")
def get_devices():
    device_map = getattr(hid_reader, 'device_map', {})
    return {
        "registered_inverters": INVERTERS_CONFIG,
        "mapped_devices_count": len(device_map),
        "mapped_devices": [
            {"id": inv_id, "path": path}
            for inv_id, path in device_map.items()
        ],
        "active_device_connected": getattr(hid_reader, 'is_connected', True)
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Solar Dashboard Backend Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
