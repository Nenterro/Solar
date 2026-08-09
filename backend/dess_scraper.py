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

    def query_device_ctrl_value(self, inverter_id: str, ctrl_id: str = "bse_battery_voltage_time_turnoff") -> Optional[float]:
        """
        Query a device control parameter value from DESSMonitor API (e.g. bse_battery_voltage_time_turnoff).
        """
        try:
            if not self.token:
                if not self.login():
                    return None

            dev = next((d for d in INVERTER_DEVICES if d["id"] == inverter_id), None)
            if not dev:
                return None

            salt = str(int(time.time() * 1000))
            q = f"&action=queryDeviceCtrlValue&source=1&i18n=en_US&pn={dev['pn']}&devcode=6443&devaddr=1&sn={dev['sn']}&id={ctrl_id}"
            sig = self._sha1(f"{salt}{self.secret}{self.token}{q}")
            p = {
                "sign": sig, "salt": salt, "token": self.token,
                "action": "queryDeviceCtrlValue", "source": "1", "i18n": "en_US",
                "pn": dev["pn"], "devcode": "6443", "devaddr": "1", "sn": dev["sn"],
                "id": ctrl_id
            }

            resp = self.session.get(DESS_BASE, params=p, timeout=15).json()
            if resp.get("err") == 0 and "dat" in resp:
                dat = resp["dat"]
                if isinstance(dat, dict) and "val" in dat:
                    return float(dat["val"])
            return None
        except Exception as e:
            logger.warning(f"Failed to query DESS ctrl {ctrl_id} for {inverter_id}: {e}")
            return None

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
                first_row = rows[0]
                first_field = first_row.get("field", [])

                if "Today generation" in col_idx:
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
                else:
                    def get_diff(name: str) -> float:
                        idx = col_idx.get(name)
                        if idx is not None and idx < len(latest_field) and idx < len(first_field):
                            try:
                                v_last = float(latest_field[idx] or 0.0)
                                v_first = float(first_field[idx] or 0.0)
                                return max(0.0, v_last - v_first)
                            except (ValueError, TypeError):
                                return 0.0
                        return 0.0

                    return {
                        "solar": round(get_diff("Total generation") / 1000.0, 1),
                        "load": round(get_diff("Total output load energy") / 1000.0, 1),
                        "gridImport": round(get_diff("Total grid energy") / 1000.0, 1),
                        "gridExport": round(get_diff("Total feed-grid energy") / 1000.0, 1),
                        "batteryCharge": round(get_diff("Total charging energy") / 1000.0, 1),
                        "batteryDischarge": round(get_diff("Total discharging energy") / 1000.0, 1)
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
            for day in sorted(aggregated.keys(), key=lambda x: int(x)):
                entry = aggregated[day]
                # Format time as YYYY-MM-DD for db.py
                full_date_str = f"{year_month}-{int(entry['time']):02d}"
                results.append({
                    "time": full_date_str,
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

    def _fetch_intraday_rows_for_device(self, sn: str, pn: str, date_str: str) -> List[Dict[str, Any]]:
        """Fetch all 10-minute intraday cumulative rows for a single inverter for a day."""
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
            resp = self.session.get(DESS_BASE, params=params, timeout=12).json()
            if resp.get("err") != 0 or "dat" not in resp:
                return []

            data = resp["dat"]
            titles = data.get("title", [])
            rows = data.get("row", [])
            if not titles or not rows:
                return []

            col_idx = {t.get("title"): i for i, t in enumerate(titles)}
            first_field = rows[0].get("field", [])
            results = []

            has_today_gen = "Today generation" in col_idx

            for r in rows:
                field = r.get("field", [])
                if len(field) <= 1:
                    continue

                ts_str = field[1] if len(field) > 1 else ""  # "YYYY-MM-DD HH:MM:SS"
                time_label = ts_str[11:16] if len(ts_str) >= 16 else ""

                def get_val(name: str) -> float:
                    idx = col_idx.get(name)
                    if idx is not None and idx < len(field):
                        try:
                            return float(field[idx] or 0.0)
                        except (ValueError, TypeError):
                            return 0.0
                    return 0.0

                def get_diff(name: str) -> float:
                    idx = col_idx.get(name)
                    if idx is not None and idx < len(field) and idx < len(first_field):
                        try:
                            v_curr = float(field[idx] or 0.0)
                            v_first = float(first_field[idx] or 0.0)
                            return max(0.0, v_curr - v_first)
                        except (ValueError, TypeError):
                            return 0.0
                    return 0.0

                if has_today_gen:
                    solar = round(get_val("Today generation") / 1000.0, 2)
                    load = round(get_val("Output load energy of day") / 1000.0, 2)
                    grid_imp = round(get_val("Grid energy of day") / 1000.0, 2)
                    grid_exp = round(get_val("Feed-grid energy of day") / 1000.0, 2)
                    bat_chg = round(get_val("Charging energy of day") / 1000.0, 2)
                    bat_dis = round(get_val("Discharging energy of day") / 1000.0, 2)
                else:
                    solar = round(get_diff("Total generation") / 1000.0, 2)
                    load = round(get_diff("Total output load energy") / 1000.0, 2)
                    grid_imp = round(get_diff("Total grid energy") / 1000.0, 2)
                    grid_exp = round(get_diff("Total feed-grid energy") / 1000.0, 2)
                    bat_chg = round(get_diff("Total charging energy") / 1000.0, 2)
                    bat_dis = round(get_diff("Total discharging energy") / 1000.0, 2)

                soc = get_val("Battery Capacity")

                if time_label:
                    results.append({
                        "time": time_label,
                        "solar": max(0.0, solar),
                        "load": max(0.0, load),
                        "gridImport": max(0.0, grid_imp),
                        "gridExport": max(0.0, grid_exp),
                        "batteryCharge": max(0.0, bat_chg),
                        "batteryDischarge": max(0.0, bat_dis),
                        "batteryLevel": soc
                    })

            return results
        except Exception as e:
            logger.warning(f"Failed to fetch intraday rows for {sn} on {date_str}: {e}")
            return []

    def fetch_cumulative_intraday_for_day(self, date_str: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
        """
        Fetch and aggregate 10-minute cumulative energy totals directly from DESSMonitor queryDeviceDataOneDay.
        Enforces monotonic increase for cumulative energy values so line graphs only go up or stay flat.
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

            time_map: Dict[str, Dict[str, Any]] = {}

            for dev in devices:
                dev_rows = self._fetch_intraday_rows_for_device(dev["sn"], dev["pn"], date_str)
                for r in dev_rows:
                    t = r["time"]
                    if t not in time_map:
                        time_map[t] = {
                            "time": t,
                            "solar": 0.0, "load": 0.0,
                            "gridImport": 0.0, "gridExport": 0.0,
                            "batteryCharge": 0.0, "batteryDischarge": 0.0,
                            "batteryLevelList": []
                        }
                    time_map[t]["solar"] += r["solar"]
                    time_map[t]["load"] += r["load"]
                    time_map[t]["gridImport"] += r["gridImport"]
                    time_map[t]["gridExport"] += r["gridExport"]
                    time_map[t]["batteryCharge"] += r["batteryCharge"]
                    time_map[t]["batteryDischarge"] += r["batteryDischarge"]
                    if r.get("batteryLevel", 0) > 0:
                        time_map[t]["batteryLevelList"].append(r["batteryLevel"])

            if not time_map:
                return []

            # Ensure 00:00 starting point
            if "00:00" not in time_map:
                time_map["00:00"] = {
                    "time": "00:00",
                    "solar": 0.0, "load": 0.0, "gridImport": 0.0,
                    "gridExport": 0.0, "batteryCharge": 0.0, "batteryDischarge": 0.0
                }

            sorted_times = sorted(time_map.keys())

            def time_to_minutes(t_str: str) -> int:
                parts = t_str.split(":")
                return int(parts[0]) * 60 + int(parts[1])

            points = []
            for t in sorted_times:
                item = time_map[t]
                m = time_to_minutes(t)
                points.append((m, t, item))

            # Build uniform 10-minute interpolated series
            max_m = points[-1][0]
            results = []

            p_idx = 0
            prev_solar, prev_load, prev_g_imp, prev_g_exp, prev_b_chg, prev_b_dis = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

            for m in range(0, max_m + 1, 10):
                while p_idx < len(points) - 1 and points[p_idx + 1][0] <= m:
                    p_idx += 1

                p1 = points[p_idx]
                m1, t1, item1 = p1[0], p1[1], p1[2]

                if p_idx < len(points) - 1:
                    p2 = points[p_idx + 1]
                    m2, t2, item2 = p2[0], p2[1], p2[2]
                else:
                    m2, item2 = m1, item1

                if m1 == m2 or m <= m1:
                    raw_s = item1["solar"]
                    raw_l = item1["load"]
                    raw_gi = item1["gridImport"]
                    raw_ge = item1["gridExport"]
                    raw_bc = item1["batteryCharge"]
                    raw_bd = item1["batteryDischarge"]
                else:
                    frac = (m - m1) / float(m2 - m1)
                    raw_s = item1["solar"] + frac * (item2["solar"] - item1["solar"])
                    raw_l = item1["load"] + frac * (item2["load"] - item1["load"])
                    raw_gi = item1["gridImport"] + frac * (item2["gridImport"] - item1["gridImport"])
                    raw_ge = item1["gridExport"] + frac * (item2["gridExport"] - item1["gridExport"])
                    raw_bc = item1["batteryCharge"] + frac * (item2["batteryCharge"] - item1["batteryCharge"])
                    raw_bd = item1["batteryDischarge"] + frac * (item2["batteryDischarge"] - item1["batteryDischarge"])

                # Monotonic non-decreasing rule
                prev_solar = max(prev_solar, raw_s)
                prev_load = max(prev_load, raw_l)
                prev_g_imp = max(prev_g_imp, raw_gi)
                prev_g_exp = max(prev_g_exp, raw_ge)
                prev_b_chg = max(prev_b_chg, raw_bc)
                prev_b_dis = max(prev_b_dis, raw_bd)

                h = m // 60
                mn = m % 60
                time_label = f"{h:02d}:{mn:02d}"

                results.append({
                    "time": time_label,
                    "solar": round(prev_solar, 2),
                    "load": round(prev_load, 2),
                    "gridImport": round(prev_g_imp, 2),
                    "gridExport": round(prev_g_exp, 2),
                    "batteryCharge": round(prev_b_chg, 2),
                    "batteryDischarge": round(prev_b_dis, 2)
                })

            return results
        except Exception as e:
            logger.error(f"Error fetching cumulative intraday for {date_str}: {e}")
            return []


dess_scraper = DESSMonitorScraper()
