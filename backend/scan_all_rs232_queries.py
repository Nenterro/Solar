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
    crc_high = (crc >> 8) & 0xFF
    crc_low = crc & 0xFF
    for b in (crc_high, crc_low):
        if b in (0x0A, 0x0D, 0x28):
            pass
    return bytes([crc_high, crc_low])

def send_cmd(port: str, cmd_str: str) -> str:
    try:
        ser = serial.Serial(port, 2400, timeout=1.5)
        cb = cmd_str.encode('ascii')
        crc = crc16(cb)
        ser.write(cb + crc + b'\r')
        resp = ser.read(512)
        ser.close()
        if len(resp) >= 3:
            return resp[:-3].decode('ascii', errors='ignore')
        return resp.decode('ascii', errors='ignore')
    except Exception as e:
        return f"ERR: {e}"

ports = {
    "inv2 (ttyUSB2)": "/dev/ttyUSB2",
    "inv3 (ttyUSB3)": "/dev/ttyUSB3"
}

queries = [
    "QPIRI", "QFLAG", "QPGS0", "QPGS1", "QPGS2", "QMOD", "QPIWS", "QDI", "QBEQI",
    "QMN", "QGMN", "QBOOT", "QPST", "QCV", "QFT", "QMD", "QCHGS", "QMUCHG",
    "QOPMP", "QET", "QEY", "QEM", "QED", "QPI", "QBYV", "QSV", "QAC2", "QAC2V",
    "QAC2OFF", "QAC", "QBAT", "QPAR", "QP2GS0", "QP3GS0", "QOPV", "QOPF",
    "QRI", "QID", "QVFW", "QVFW2", "QPR", "QP1", "QP2", "QP3"
]

print("==========================================================")
print("DEEP RS232 QUERY SCAN FOR AC2 VOLTAGE REGISTERS (50.0 / 52.0 / 56.5 / 56.6)")
print("==========================================================")

for name, port in ports.items():
    print(f"\n--- SCANNING {name} ({port}) ---")
    for q in queries:
        resp = send_cmd(port, q)
        if resp and not resp.startswith("ERR") and not resp.startswith("(NAK"):
            print(f"  {q:10s} -> RAW: {resp}")
            tokens = resp.replace('(', '').split()
            for idx, tok in enumerate(tokens):
                if any(target in tok for target in ["50.", "52.", "56.5", "56.6", "566", "565", "520", "500"]):
                    print(f"    *** MATCH FOUND in {q} index [{idx}]: token='{tok}' ***")
        elif resp.startswith("(NAK"):
            pass
        else:
            print(f"  {q:10s} -> {resp}")
