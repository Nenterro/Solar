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

def test_cmd(port, cmd):
    try:
        ser = serial.Serial(port, 2400, timeout=1.0)
        cb = cmd.encode('ascii')
        ser.write(cb + crc16(cb) + b'\r')
        res = ser.read(128).decode('ascii', errors='ignore')
        ser.close()
        return res
    except Exception as e:
        return str(e)

cmds = ['PBT52.0', 'PBT56.5', 'PBA54.0', 'PBA57.0', 'PAC2OFF52.0', 'PAC2ON57.0', 'PSAC252.0', 'PDAC252.0', 'PAC252.0']
for p in ['/dev/ttyUSB2', '/dev/ttyUSB3']:
    print(f"=== PORT {p} ===", flush=True)
    for c in cmds:
        print(f"  {c:15s} -> {repr(test_cmd(p, c))}", flush=True)
        time.sleep(0.1)
