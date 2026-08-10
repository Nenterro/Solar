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
    return bytes([crc_high, crc_low])

def send_cmd(port: str, cmd_str: str) -> str:
    try:
        ser = serial.Serial(port, 2400, timeout=1.0)
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

port = "/dev/ttyUSB3" # inv3 (which has AC2 turn off = 56.5 / 56.6)

test_cmds = [
    "QPIRI", "QPIRI2", "QPIR2", "QFLAG", "QPGS0", "QPGS1", "QPGS2", "QBEQI",
    "QDI", "QFT", "QBOOT", "QGMN", "QMN", "QPST", "QCV", "QFT", "QMD",
    "QPGS3", "QPGS4", "QPIRP", "QPIRG", "QSET", "QSETTINGS", "QALL",
    "QPR", "QP1", "QP2", "QP3", "QAC2", "QAC2V", "PAC2OFF", "PAC2ON"
]

print("=== SCANNING INVERTER 3 (/dev/ttyUSB3) FOR AC2 VOLTAGE (56.5 / 56.6) ===")
for cmd in test_cmds:
    time.sleep(0.1)
    res = send_cmd(port, cmd)
    if res and not res.startswith("ERR") and not res.startswith("(NAK"):
        print(f"  {cmd:12s} -> RAW: {res}")
    elif res.startswith("(NAK"):
        print(f"  {cmd:12s} -> NAK")
    else:
        print(f"  {cmd:12s} -> {res}")
