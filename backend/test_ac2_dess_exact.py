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
body = session.get(DESS_BASE, params=params, timeout=15).json()
token = body["dat"]["token"]
secret = body["dat"]["secret"]

inverters = [
    {"id": "inv1", "sn": "96342504101941", "pn": "E50000221645100626"},
    {"id": "inv2", "sn": "96342504101900", "pn": "E50000250526194186"},
    {"id": "inv3", "sn": "96342504102056", "pn": "E50000250513164327"},
]

target_ids = [
    "bse_battery_voltage_time_turnoff",
    "bse_battery_voltage_time_turnon"
]

for inv in inverters:
    print(f"\n=== INVERTER {inv['id']} ({inv['sn']}) ===", flush=True)
    for ctrl_id in target_ids:
        salt = str(int(time.time() * 1000))
        q = f"&action=queryDeviceCtrlValue&source=1&i18n=en_US&pn={inv['pn']}&devcode=6443&devaddr=1&sn={inv['sn']}&id={ctrl_id}"
        sig = _sha1(f"{salt}{secret}{token}{q}")
        p = {
            "sign": sig, "salt": salt, "token": token,
            "action": "queryDeviceCtrlValue", "source": "1", "i18n": "en_US",
            "pn": inv["pn"], "devcode": "6443", "devaddr": "1", "sn": inv["sn"],
            "id": ctrl_id
        }
        try:
            r = session.get(DESS_BASE, params=p, timeout=20).json()
            if r.get("err") == 0:
                print(f"  {ctrl_id} -> {r.get('dat')}", flush=True)
            else:
                print(f"  {ctrl_id} -> ERR: {r.get('desc')}", flush=True)
        except Exception as e:
            print(f"  {ctrl_id} -> TIMEOUT/ERR: {e}", flush=True)
        time.sleep(1.0)
