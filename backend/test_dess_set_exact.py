import time, requests, hashlib

DESS_USER = 'Jawad-HybridKnox'
DESS_PASS = 'sadeem1234'
DESS_BASE = 'https://web.dessmonitor.com/public/'
COMPANY_KEY = 'bnrl_frRFjEz8Mkn'

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()

salt = str(int(time.time() * 1000))
pass_hash = _sha1(DESS_PASS)
query = f"&action=authSource&usr={DESS_USER}&source=1&company-key={COMPANY_KEY}"
sign = _sha1(f"{salt}{pass_hash}{query}")
params = {
    "sign": sign, "salt": salt,
    "action": "authSource", "usr": DESS_USER,
    "source": "1", "company-key": COMPANY_KEY,
}
body = session.get(DESS_BASE, params=params, timeout=10).json()
token = body["dat"]["token"]
secret = body["dat"]["secret"]

# inv3 (sn=96342504102056, pn=E50000250513164327)
sn = "96342504102056"
pn = "E50000250513164327"

salt = str(int(time.time() * 1000))
q = f"&action=setDeviceCtrlValue&source=1&i18n=en_US&pn={pn}&devcode=6443&devaddr=1&sn={sn}&id=bse_battery_voltage_time_turnoff&val=54.0"
sig = _sha1(f"{salt}{secret}{token}{q}")

params = {
    "sign": sig, "salt": salt, "token": token,
    "action": "setDeviceCtrlValue", "source": "1", "i18n": "en_US",
    "pn": pn, "devcode": "6443", "devaddr": "1", "sn": sn,
    "id": "bse_battery_voltage_time_turnoff", "val": "54.0"
}

# Try POST with query params in URL
url_with_params = f"{DESS_BASE}?sign={sig}&salt={salt}&token={token}&action=setDeviceCtrlValue&source=1&pn={pn}&sn={sn}&devcode=6443&devaddr=1&id=bse_battery_voltage_time_turnoff&val=54.0&i18n=en_US"

try:
    resp = session.post(url_with_params, timeout=15).json()
    print("EXACT POST RESPONSE:", resp)
except Exception as e:
    print("ERR:", e)
