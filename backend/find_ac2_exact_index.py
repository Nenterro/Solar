import serial, time

def crc16(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return bytes([(crc >> 8) & 0xFF, crc & 0xFF])

def send_cmd(port: str, cmd_str: str) -> str:
    try:
        ser = serial.Serial(port, 2400, timeout=1.0)
        cb = cmd_str.encode('ascii')
        ser.write(cb + crc16(cb) + b'\r')
        resp = ser.read(512).decode('ascii', errors='ignore')
        ser.close()
        if len(resp) >= 3:
            return resp[:-3]
        return resp
    except Exception as e:
        return f"ERR: {e}"

ports = {
    "inv1": "/dev/ttyUSB1", # expected AC2 turn off = 52 or 52.0
    "inv2": "/dev/ttyUSB2", # expected AC2 turn off = 50 or 50.0
    "inv3": "/dev/ttyUSB3"  # expected AC2 turn off = 54 or 54.0
}

expected_vals = {
    "inv1": ["52", "52.0", "520"],
    "inv2": ["50", "50.0", "500"],
    "inv3": ["54", "54.0", "540"]
}

# Extensive Voltronic query commands list
queries = [
    "QPIRI", "QFLAG", "QPGS0", "QPGS1", "QPGS2", "QMOD", "QPIWS", "QDI", "QBEQI",
    "QMN", "QGMN", "QBOOT", "QPST", "QCV", "QFT", "QMD", "QCHGS", "QMUCHG",
    "QOPMP", "QET", "QEY", "QEM", "QED", "QPI", "QBYV", "QSV", "QAC2", "QAC2V",
    "QAC2OFF", "QAC", "QBAT", "QPAR", "QP2GS0", "QP3GS0", "QOPV", "QOPF",
    "QRI", "QID", "QVFW", "QVFW2", "QPR", "QP1", "QP2", "QP3", "QSET", "QSETTINGS",
    "QFLAG2", "QPIR2", "QPIRI2", "QPAR2", "QSTAT"
]

results = {} # inv_id -> { query_cmd -> raw_response }

print("=========================================================================")
print("SEARCHING ALL RS232 QUERIES FOR PATTERN: Inv1=52.0, Inv2=50.0, Inv3=54.0")
print("=========================================================================")

for inv_id, port in ports.items():
    results[inv_id] = {}
    print(f"\n--- Reading {inv_id.upper()} ({port}) ---", flush=True)
    for q in queries:
        resp = send_cmd(port, q)
        if resp and not resp.startswith("ERR") and not resp.startswith("(NAK"):
            results[inv_id][q] = resp
            print(f"  {q:10s} -> RAW: {resp}", flush=True)
        time.sleep(0.05)

print("\n=========================================================================")
print("ANALYZING MATCHING REGISTERS ACROSS ALL 3 INVERTERS")
print("=========================================================================")

all_queries = set(results["inv1"].keys()) & set(results["inv2"].keys()) & set(results["inv3"].keys())

for q in sorted(all_queries):
    r1 = results["inv1"][q]
    r2 = results["inv2"][q]
    r3 = results["inv3"][q]
    
    t1 = r1.replace('(', '').split()
    t2 = r2.replace('(', '').split()
    t3 = r3.replace('(', '').split()
    
    # Check token by token
    min_len = min(len(t1), len(t2), len(t3))
    for i in range(min_len):
        v1, v2, v3 = t1[i], t2[i], t3[i]
        # Check if v1 matches 52, v2 matches 50, v3 matches 54
        if (any(ex in v1 for ex in expected_vals["inv1"]) and
            any(ex in v2 for ex in expected_vals["inv2"]) and
            any(ex in v3 for ex in expected_vals["inv3"])):
            print(f"!!! MATCH FOUND in Command '{q}' Index [{i}]:")
            print(f"    Inv1 ({v1}) | Inv2 ({v2}) | Inv3 ({v3})")
            print(f"    Raw Inv1: {r1}")
            print(f"    Raw Inv2: {r2}")
            print(f"    Raw Inv3: {r3}\n")
