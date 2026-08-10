import requests, hashlib, time

DESS_USER = 'Jawad-HybridKnox'
DESS_PASS = 'sadeem1234'
DESS_BASE = 'https://web.dessmonitor.com/public/'
COMPANY_KEY = 'bnrl_frRFjEz8Mkn'

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()

# 1. Login
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
print("Auth Token:", token[:10])

# 2. Query Device Parameters / Controls / Settings
sn = "96342504101900"
pn = "E50000250526194186"

actions_to_test = [
    "queryDeviceDataOneDay",
    "queryDeviceParam",
    "queryDeviceLastData",
    "getDeviceSetting",
    "getDeviceControl",
    "getSettingList",
    "getDeviceSettingParam"
]

for act in actions_to_test:
    salt = str(int(time.time() * 1000))
    q = f"&action={act}&source=1&i18n=en_US&pn={pn}&devcode=6443&devaddr=1&sn={sn}"
    sig = _sha1(f"{salt}{secret}{token}{q}")
    p = {
        "sign": sig, "salt": salt, "token": token,
        "action": act, "source": "1", "i18n": "en_US",
        "pn": pn, "devcode": "6443", "devaddr": "1", "sn": sn
    }
    try:
        r = session.get(DESS_BASE, params=p, timeout=10).json()
        print(f"\n--- Action {act} ---")
        if r.get("err") == 0:
            print("DAT:", str(r.get("dat"))[:800])
        else:
            print("ERR/DESC:", r.get("desc"), r.get("err"))
    except Exception as e:
        print("ERR:", e)
