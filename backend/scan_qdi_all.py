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

ports = {
    "inv1": "/dev/ttyUSB1",
    "inv2": "/dev/ttyUSB2",
    "inv3": "/dev/ttyUSB3"
}

for name, port in ports.items():
    res = query(port, "QDI")
    print(f"{name} ({port}) QDI -> {repr(res)}")
