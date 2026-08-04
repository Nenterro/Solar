import hashlib, time, requests, json

DESS_BASE = "https://web.dessmonitor.com/public/"
COMPANY_KEY = "bnrl_frRFjEz8Mkn"
USER = "Jawad-HybridKnox"
PASS = "sadeem1234"
SN = "96342504102056"
PN = "E50000250513164327"

def sha1(t): return hashlib.sha1(t.encode()).hexdigest()

http = requests.Session()
http.headers.update({"User-Agent": "Mozilla/5.0"})

# Login
salt = str(int(time.time() * 1000))
pass_hash = sha1(PASS)
query = f"&action=authSource&usr={USER}&source=1&company-key={COMPANY_KEY}"
sign = sha1(f"{salt}{pass_hash}{query}")
params = {"sign": sign, "salt": salt, "action": "authSource", "usr": USER, "source": "1", "company-key": COMPANY_KEY}
body = http.get(DESS_BASE, params=params).json()
token = body["dat"]["token"]
secret = body["dat"]["secret"]
print("Login OK")

# Monthly query
salt  = str(int(time.time() * 1000))
param_id = "ENERGY_TODAY,LOAD_ENERGY_TODAY"
date_str = "2026-07"
query = (
    f"&action=querySPDeviceKeyParameterMonthPerDay&source=1"
    f"&pn={PN}&sn={SN}&devcode=6443&devaddr=1"
    f"&i18n=en_US&parameter={param_id}&chartStatus=false&date={date_str}"
)
sign = sha1(f"{salt}{secret}{token}{query}")

# Use exact params as test_dess12.py
params = {
    "sign": sign, "salt": salt, "token": token,
    "action": "querySPDeviceKeyParameterMonthPerDay", "source": "1",
    "pn": PN, "sn": SN, "devcode": "6443", "devaddr": "1",
    "i18n": "en_US", "parameter": param_id,
    "chartStatus": "false", "date": date_str
}

resp = http.get(DESS_BASE, params=params).json()
print("err:", resp.get("err"))
if resp.get("err") == 0:
    print("SUCCESS!")
    dat = resp["dat"]
    for k in dat:
        if isinstance(dat[k], dict):
            data_list = dat[k].get("data", [])
            print(f"  {k}: {len(data_list)} days")
else:
    print("desc:", resp.get("desc"))
