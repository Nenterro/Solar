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

ports = {
    "inv1": "/dev/ttyUSB1",
    "inv2": "/dev/ttyUSB2",
    "inv3": "/dev/ttyUSB3"
}

test_cmds = [
    "QPIRI", "QFLAG", "QPGS0", "QPGS1", "QBEQI", "QDI", "QFT", "QMN", "QGMN", "QPST", "QCV", "QMD"
]

print("=========================================================================")
print("EXHAUSTIVE RS232 PARAMETER SCAN ACROSS ALL 3 INVERTERS")
print("=========================================================================")

for name, port in ports.items():
    print(f"\n=================== {name.upper()} ({port}) ===================")
    for cmd in test_cmds:
        res = send_cmd(port, cmd)
        if res and not res.startswith("ERR") and not res.startswith("(NAK"):
            print(f"  {cmd:10s} -> RAW: {res}")
        elif res.startswith("(NAK"):
            print(f"  {cmd:10s} -> (NAK)")
        else:
            print(f"  {cmd:10s} -> {res}")
        time.sleep(0.1)
