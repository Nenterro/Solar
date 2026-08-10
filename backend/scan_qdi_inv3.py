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

def query(port, cmd):
    try:
        ser = serial.Serial(port, 2400, timeout=1.5)
        cb = cmd.encode('ascii')
        ser.write(cb + crc16(cb) + b'\r')
        res = ser.read(256).decode('ascii', errors='ignore')
        ser.close()
        return res
    except Exception as e:
        return str(e)

print("=== QUERYING QDI ON INVERTER 3 (/dev/ttyUSB3) ===", flush=True)
res = query("/dev/ttyUSB3", "QDI")
print("QDI RAW:", repr(res))
if res.startswith("("):
    tokens = res[1:].split()
    for idx, tok in enumerate(tokens):
        print(f"  Index [{idx:2d}]: {tok}")
