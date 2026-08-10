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

def test_set(port: str, cmd_str: str) -> str:
    try:
        ser = serial.Serial(port, 2400, timeout=2.0)
        cb = cmd_str.encode('ascii')
        crc = crc16(cb)
        ser.write(cb + crc + b'\r')
        resp = ser.read(256)
        ser.close()
        return resp.decode('ascii', errors='ignore')
    except Exception as e:
        return f"ERR: {e}"

# Test candidates for AC2 Turn Off voltage (56.5V or 52.0V or 50.0V) and Turn On voltage (54.0V or 57.0V)
commands_to_test = [
    "PBT52.0", "PBT50.0", "PBT56.5", "PBT56.6",
    "PBA54.0", "PBA57.0",
    "PAC2OFF52.0", "PAC2OFF56.5",
    "PAC2ON54.0", "PAC2ON57.0",
    "PSAC252.0", "PDAC252.0",
    "PAC52.0", "PAC56.5"
]

print("=== TESTING AC2 RS232 SET COMMANDS ON INV2 (/dev/ttyUSB2) ===")
for cmd in commands_to_test:
    res = test_set("/dev/ttyUSB2", cmd)
    print(f"  {cmd:15s} -> {res.strip()}")
    time.sleep(0.2)
