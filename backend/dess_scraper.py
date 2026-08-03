import os
import time
import hashlib
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger("DESS_SCRAPER")

DESS_USER = os.getenv("DESS_USER", "Jawad-HybridKnox")
DESS_PASS = os.getenv("DESS_PASS", "sadeem1234")
DESS_BASE = "https://web.dessmonitor.com/public/"
COMPANY_KEY = "bnrl_frRFjEz8Mkn"

# Each inverter has its own SN + PN pair
INVERTER_DEVICES = [
    {"id": "inv1", "sn": "96342504101941", "pn": "E50000221645100626"},
    {"id": "inv2", "sn": "96342504101900", "pn": "E50000250526194186"},
    {"id": "inv3", "sn": "96342504102056", "pn": "E50000250513164327"},
]

# Parameters that hold daily kWh totals on the DESS API
DAILY_ENERGY_PARAMS = "ENERGY_TODAY,LOAD_ENERGY_TODAY"


class DESSMonitorScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.token = ""
        self.secret = ""

    def _sha1(self, text: str) -> str:
        return hashlib.sha1(text.encode()).hexdigest()

    def login(self) -> bool:
        """Authenticate with DESSMonitor public API using SHA1 signature auth."""
        try:
            salt = str(int(time.time() * 1000))
            pass_hash = self._sha1(DESS_PASS)
            query = f"&action=authSource&usr={DESS_USER}&source=1&company-key={COMPANY_KEY}"
            sign = self._sha1(f"{salt}{pass_hash}{query}")

            params = {
                "sign": sign, "salt": salt,
                "action": "authSource", "usr": DESS_USER,
                "source": "1", "company-key": COMPANY_KEY,
            }
            body = self.session.get(DESS_BASE, params=params, timeout=15).json()

            if body.get("err") == 0 and "dat" in body:
                self.token = body["dat"]["token"]
                self.secret = body["dat"]["secret"]
                logger.info(f"DESSMonitor login successful (token={self.token[:8]}...)")
                return True
            else:
                logger.error(f"DESSMonitor login failed: {body.get('desc', body)}")
                return False
        except Exception as e:
            logger.error(f"DESSMonitor login exception: {e}")
            return False

    def _fetch_daily_totals_for_day(self, sn: str, pn: str, date_str: str) -> Optional[Dict[str, float]]:
        """Fetch data for a single day using the reliable queryDeviceDataOneDay action."""
        salt = str(int(time.time() * 1000))
        query = (
            f"&action=queryDeviceDataOneDay&source=1"
            f"&i18n=en_US&pn={pn}&devcode=6443&devaddr=1&sn={sn}&date={date_str}"
        )
        sign = self._sha1(f"{salt}{self.secret}{self.token}{query}")
        
        params = {
            "sign": sign, "salt": salt, "token": self.token, 
            "action": "queryDeviceDataOneDay", "source": "1", 
            "i18n": "en_US", 
            "pn": pn, "devcode": "6443", "devaddr": "1", "sn": sn, "date": date_str
        }
        
        try:
            resp = self.session.get(DESS_BASE, params=params, timeout=10).json()
            if resp.get("err") == 0 and "dat" in resp:
                data = resp["dat"]
                titles = data.get("title", [])
                rows = data.get("row", [])
                if not titles or not rows:
                    return None
                
                col_idx = {t.get("title"): i for i, t in enumerate(titles)}
                latest_row = rows[-1]
                latest_field = latest_row.get("field", [])
                
                def get_val(name: str) -> float:
                    idx = col_idx.get(name)
                    if idx is not None and idx < len(latest_field):
                        try:
                            return float(latest_field[idx] or 0.0)
                        except (ValueError, TypeError):
                            return 0.0
                    return 0.0
                
                return {
                    "solar": round(get_val("Today generation") / 1000.0, 1),
                    "load": round(get_val("Output load energy of day") / 1000.0, 1),
                    "gridImport": round(get_val("Grid energy of day") / 1000.0, 1),
                    "gridExport": round(get_val("Feed-grid energy of day") / 1000.0, 1),
                    "batteryCharge": round(get_val("Charging energy of day") / 1000.0, 1),
                    "batteryDischarge": round(get_val("Discharging energy of day") / 1000.0, 1)
                }
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch {date_str} for {sn}: {e}")
            return None

    def _fetch_month_daily_totals(self, sn: str, pn: str, year_month: str) -> List[Dict[str, Any]]:
        """
        Fetch daily kWh totals for one inverter for a given month by fetching each day.
        """
        import calendar
        from datetime import datetime, date
        
        try:
            y, m = map(int, year_month.split("-"))
            _, last_day = calendar.monthrange(y, m)
        except ValueError:
            return []

        # Don't fetch into the future
        today = datetime.now().date()
        if y == today.year and m == today.month:
            last_day = today.day
        elif y > today.year or (y == today.year and m > today.month):
            return []

        results = []
        for day in range(1, last_day + 1):
            date_str = f"{y:04d}-{m:02d}-{day:02d}"
            totals = self._fetch_daily_totals_for_day(sn, pn, date_str)
            if totals:
                results.append({
                    "time": str(day),
                    "solar": totals["solar"],
                    "load": totals["load"],
                    "gridImport": totals["gridImport"],
                    "gridExport": totals["gridExport"],
                    "batteryCharge": totals["batteryCharge"],
                    "batteryDischarge": totals["batteryDischarge"]
                })
            else:
                # Fill zeros if no data for the day
                results.append({
                    "time": str(day),
                    "solar": 0.0, "load": 0.0,
                    "gridImport": 0.0, "gridExport": 0.0,
                    "batteryCharge": 0.0, "batteryDischarge": 0.0
                })
            # Slight delay to avoid hammering the API
            time.sleep(0.1)
            
        return results

    def fetch_daily_totals_for_day(self, date_str: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
        """
        Fetch daily kWh totals for a specific single day.
        Aggregates across all 3 inverters when inverter_id is 'all'.
        """
        try:
            if not self.token:
                if not self.login():
                    return []

            if inverter_id == "all":
                devices = INVERTER_DEVICES
            else:
                devices = [d for d in INVERTER_DEVICES if d["id"] == inverter_id]
                if not devices:
                    devices = INVERTER_DEVICES

            aggregated = {
                "time": date_str[-2:],  # Use just the day number for consistency if needed, or date_str
                "solar": 0.0, "load": 0.0,
                "gridImport": 0.0, "gridExport": 0.0,
                "batteryCharge": 0.0, "batteryDischarge": 0.0
            }
            
            # Note: For consistency with how db.py expects time format (YYYY-MM-DD)
            # we will return date_str as "time"
            aggregated["time"] = date_str

            for dev in devices:
                totals = self._fetch_daily_totals_for_day(dev["sn"], dev["pn"], date_str)
                if not totals:
                    continue

                aggregated["solar"] += totals.get("solar", 0.0)
                aggregated["load"] += totals.get("load", 0.0)
                aggregated["gridImport"] += totals.get("gridImport", 0.0)
                aggregated["gridExport"] += totals.get("gridExport", 0.0)
                aggregated["batteryCharge"] += totals.get("batteryCharge", 0.0)
                aggregated["batteryDischarge"] += totals.get("batteryDischarge", 0.0)

            # Round off the aggregated values
            for k in ["solar", "load", "gridImport", "gridExport", "batteryCharge", "batteryDischarge"]:
                aggregated[k] = round(aggregated[k], 1)

            return [aggregated]
        except Exception as e:
            logger.error(f"Error fetching daily totals for {date_str} from DESS: {e}")
            return []

    def fetch_daily_totals_for_month(self, year_month: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
        """
        Fetch daily kWh totals for a given month (YYYY-MM) from DESSMonitor cloud.
        Aggregates across all 3 inverters when inverter_id is "all".
        """
        try:
            # Ensure we have a valid session
            if not self.token:
                if not self.login():
                    return []

            # Determine which inverter(s) to query
            if inverter_id == "all":
                devices = INVERTER_DEVICES
            else:
                devices = [d for d in INVERTER_DEVICES if d["id"] == inverter_id]
                if not devices:
                    devices = INVERTER_DEVICES  # fallback to all

            # Fetch data for each inverter and aggregate
            aggregated = {}  # day_str -> {solar, load, ...}

            for dev in devices:
                records = self._fetch_month_daily_totals(dev["sn"], dev["pn"], year_month)
                
                if records is None:
                    # Possible auth expiry — re-login and retry once
                    logger.warning(f"DESS API returned error for {dev['id']}, re-authenticating...")
                    self.token = ""
                    if self.login():
                        records = self._fetch_month_daily_totals(dev["sn"], dev["pn"], year_month)
                    if not records:
                        continue

                for rec in records:
                    day = rec["time"]
                    if day not in aggregated:
                        aggregated[day] = {
                            "time": day,
                            "solar": 0.0, "load": 0.0,
                            "gridImport": 0.0, "gridExport": 0.0,
                            "batteryCharge": 0.0, "batteryDischarge": 0.0
                        }
                    aggregated[day]["solar"] += rec.get("solar", 0.0)
                    aggregated[day]["load"] += rec.get("load", 0.0)
                    aggregated[day]["gridImport"] += rec.get("gridImport", 0.0)
                    aggregated[day]["gridExport"] += rec.get("gridExport", 0.0)
                    aggregated[day]["batteryCharge"] += rec.get("batteryCharge", 0.0)
                    aggregated[day]["batteryDischarge"] += rec.get("batteryDischarge", 0.0)

                time.sleep(0.3)  # Rate limiting between inverter queries

            # Round aggregated values and sort by date
            results = []
            for day in sorted(aggregated.keys()):
                entry = aggregated[day]
                results.append({
                    "time": entry["time"],
                    "solar": round(entry["solar"], 1),
                    "load": round(entry["load"], 1),
                    "gridImport": round(entry["gridImport"], 1),
                    "gridExport": round(entry["gridExport"], 1),
                    "batteryCharge": round(entry["batteryCharge"], 1),
                    "batteryDischarge": round(entry["batteryDischarge"], 1)
                })

            logger.info(f"DESS fetched {len(results)} daily records for {year_month} ({inverter_id})")
            return results

        except Exception as e:
            logger.error(f"Error fetching monthly totals from DESS: {e}")
            return []


dess_scraper = DESSMonitorScraper()
