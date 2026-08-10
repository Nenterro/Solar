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

actions_to_try = [
    "setDeviceCtrlValue",
    "sendDeviceCtrlValue",
    "setDeviceControlValue",
    "writeDeviceCtrlValue",
    "setControlValue"
]

print("=== TESTING DESS SET CONTROL API VIA POST AND GET ===", flush=True)

for act in actions_to_try:
    salt = str(int(time.time() * 1000))
    q = f"&action={act}&source=1&i18n=en_US&pn={pn}&devcode=6443&devaddr=1&sn={sn}&id=bse_battery_voltage_time_turnoff&val=54.0"
    sig = _sha1(f"{salt}{secret}{token}{q}")
    
    # 1. GET Test
    p_get = {
        "sign": sig, "salt": salt, "token": token,
        "action": act, "source": "1", "i18n": "en_US",
        "pn": pn, "devcode": "6443", "devaddr": "1", "sn": sn,
        "id": "bse_battery_voltage_time_turnoff", "val": "54.0"
    }
    try:
        r = session.get(DESS_BASE, params=p_get, timeout=5).json()
        print(f"GET {act:25s} -> {r}", flush=True)
    except Exception as e:
        print(f"GET {act:25s} -> ERR: {e}", flush=True)

    # 2. POST Test
    try:
        r_post = session.post(DESS_BASE, data=p_get, timeout=5).json()
        print(f"POST {act:25s} -> {r_post}", flush=True)
    except Exception as e:
        print(f"POST {act:25s} -> ERR: {e}", flush=True)
