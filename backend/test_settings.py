import serial, time, re

def crc16_voltronic(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    low = crc & 0xFF
    high = (crc >> 8) & 0xFF
    if low in (0x28, 0x0D, 0x0A): low += 1
    if high in (0x28, 0x0D, 0x0A): high += 1
    return bytes([high, low])

def query_cmd(port, cmd):
    try:
        ser = serial.Serial(port, 2400, timeout=1.5)
        cb = cmd.encode('ascii')
        full_cmd = cb + crc16_voltronic(cb) + b'\r'
        ser.reset_input_buffer()
        ser.write(full_cmd)
        resp = ser.read_until(b'\r', size=150)
        ser.close()
        return resp
    except Exception as e:
        return f"Error: {e}".encode()

ports = {'inv3': '/dev/ttyUSB1', 'inv2': '/dev/ttyUSB2'}
cmds = ['QPIRI', 'QFLAG', 'QPIGS', 'QET']

for inv, p in ports.items():
    print(f'=== Querying {inv} on {p} ===')
    for c in cmds:
        resp = query_cmd(p, c)
        print(f'{c} -> {resp}')
        time.sleep(0.2)
