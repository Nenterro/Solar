import requests, hashlib, time

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

sn = "96342504101900"
pn = "E50000250526194186"

action_candidates = [
    "queryDeviceSetting", "queryDeviceControl", "getDeviceSettingInfo",
    "queryDeviceConfig", "setDeviceParam", "setDeviceControl", "readDeviceParam",
    "queryControlParam", "getDeviceParameter", "queryDeviceParameters",
    "getDevSetting", "getDevParam", "queryDevSetting", "queryDevControl",
    "queryParam", "queryParameter", "queryDeviceSettingList", "queryDeviceControlList",
    "getDeviceSettingList", "getDeviceControlList", "queryDeviceRemoteParam"
]

print("Testing DESS API action names...")
for act in action_candidates:
    salt = str(int(time.time() * 1000))
    q = f"&action={act}&source=1&i18n=en_US&pn={pn}&devcode=6443&devaddr=1&sn={sn}"
    sig = _sha1(f"{salt}{secret}{token}{q}")
    p = {
        "sign": sig, "salt": salt, "token": token,
        "action": act, "source": "1", "i18n": "en_US",
        "pn": pn, "devcode": "6443", "devaddr": "1", "sn": sn
    }
    try:
        r = session.get(DESS_BASE, params=p, timeout=5).json()
        desc = r.get("desc", str(r))
        if "can not found action" not in desc and "not found action" not in desc:
            print(f"!!! FOUND VALID DESS ACTION: {act} -> {r}")
    except Exception as e:
        pass
