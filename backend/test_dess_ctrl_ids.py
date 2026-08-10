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

# 1. Try querying control list first
salt = str(int(time.time() * 1000))
q = f"&action=queryDeviceCtrlList&source=1&i18n=en_US&pn={pn}&devcode=6443&devaddr=1&sn={sn}"
sig = _sha1(f"{salt}{secret}{token}{q}")
p = {
    "sign": sig, "salt": salt, "token": token,
    "action": "queryDeviceCtrlList", "source": "1", "i18n": "en_US",
    "pn": pn, "devcode": "6443", "devaddr": "1", "sn": sn
}
try:
    r = session.get(DESS_BASE, params=p, timeout=10).json()
    print("queryDeviceCtrlList:", r)
except Exception as e:
    print("queryDeviceCtrlList err:", e)

# 2. Test candidate IDs
turn_on_ids = [
    "bse_battery_voltage_time_turnon",
    "bse_battery_voltage_time_turn_on",
    "bse_battery_voltage_to_turnon",
    "bse_battery_voltage_to_turn_on",
    "bse_battery_voltage_turnon",
    "bse_battery_voltage_turn_on",
    "bse_battery_voltage_time_recovery",
    "bse_battery_voltage_time_reconnect",
    "bse_battery_voltage_back_charging",
    "bse_battery_voltage_back_to_charging",
    "bse_battery_voltage_time_back_charging",
    "bse_battery_voltage_time_on"
]

print("\nTesting Turn-On Candidate IDs...")
for cid in turn_on_ids:
    salt = str(int(time.time() * 1000))
    q = f"&action=queryDeviceCtrlValue&source=1&i18n=en_US&pn={pn}&devcode=6443&devaddr=1&sn={sn}&id={cid}"
    sig = _sha1(f"{salt}{secret}{token}{q}")
    p = {
        "sign": sig, "salt": salt, "token": token,
        "action": "queryDeviceCtrlValue", "source": "1", "i18n": "en_US",
        "pn": pn, "devcode": "6443", "devaddr": "1", "sn": sn,
        "id": cid
    }
    try:
        r = session.get(DESS_BASE, params=p, timeout=8).json()
        desc = r.get("desc", str(r))
        if "can not found id" not in desc and "not found" not in desc:
            print(f"!!! FOUND VALID TURN-ON ID: {cid} -> {r}")
        else:
            print(f"  {cid:40s} -> NOT FOUND")
    except Exception as e:
        print(f"  {cid:40s} -> TIMEOUT ({e})")
