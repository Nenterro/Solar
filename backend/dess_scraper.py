import os
import time
import hashlib
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger("DESS_SCRAPER")

DESS_USER = os.getenv("DESS_USER", "Jawad-HybridKnox")
DESS_PASS = os.getenv("DESS_PASS", "sadeem1234")
DESS_BASE = "https://web.dessmonitor.com/api"
COMPANY_KEY = "knox"

class DESSMonitorScraper:
    def __init__(self):
        self.session = requests.Session()
        self.secret_token = None
        self.user_id = None
        self.inverter_pn = "96342504123"

    def login(self) -> bool:
        """
        Authenticate with DESSMonitor web API.
        """
        try:
            pwd_md5 = hashlib.md5(DESS_PASS.encode()).hexdigest()
            url = f"{DESS_BASE}/user/login"
            params = {
                "account": DESS_USER,
                "password": pwd_md5,
                "company_key": COMPANY_KEY,
                "client": "web"
            }
            res = self.session.get(url, params=params, timeout=15).json()

            if res.get("err") == 0 and "dat" in res:
                dat = res["dat"]
                self.secret_token = dat.get("secret")
                self.user_id = dat.get("id")
                logger.info(f"DESSMonitor login successful for user_id={self.user_id}")
                return True
            else:
                logger.error(f"DESSMonitor login failed: {res.get('desc')}")
                return False
        except Exception as e:
            logger.error(f"DESSMonitor login exception: {e}")
            return False

    def fetch_daily_totals_for_month(self, year_month: str, inverter_id: str = "all") -> List[Dict[str, Any]]:
        """
        Fetch daily kWh totals for a given month (YYYY-MM) from DESSMonitor cloud.
        Used ONLY for current day 10-min polling and explicit manual backfill.
        """
        try:
            if not self.secret_token:
                if not self.login():
                    return []

            params = {
                "secret": self.secret_token,
                "pn": self.inverter_pn,
                "devcode": "2400",
                "devaddr": "1",
                "sn": self.inverter_pn,
                "type": "month",
                "date": year_month
            }

            url = f"{DESS_BASE}/device/energy/chart"
            res = self.session.get(url, params=params, timeout=15).json()

            if res.get("err") == 0 and "dat" in res:
                raw_list = res["dat"].get("output", [])
                results = []
                for item in raw_list:
                    # Output structure: [date_str, solar, load, grid_imp, grid_exp, bat_chg, bat_dis]
                    if len(item) >= 7:
                        d_str = str(item[0])
                        solar_val = float(item[1] or 0.0)
                        grid_imp_val = float(item[3] or 0.0)

                        # Filter out Day 1 cumulative register corruption outlier
                        if solar_val > 300.0 or grid_imp_val > 300.0:
                            continue

                        results.append({
                            "time": d_str,
                            "solar": round(solar_val, 1),
                            "load": round(float(item[2] or 0.0), 1),
                            "gridImport": round(grid_imp_val, 1),
                            "gridExport": round(float(item[4] or 0.0), 1),
                            "batteryCharge": round(float(item[5] or 0.0), 1),
                            "batteryDischarge": round(float(item[6] or 0.0), 1)
                        })
                return results
            return []
        except Exception as e:
            logger.error(f"Error fetching monthly totals from DESS: {e}")
            return []

dess_scraper = DESSMonitorScraper()
