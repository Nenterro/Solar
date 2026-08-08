import serial, time

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
        ser = serial.Serial(port, 2400, timeout=1.0)
        cb = cmd.encode('ascii')
        full_cmd = cb + crc16_voltronic(cb) + b'\r'
        ser.reset_input_buffer()
        ser.write(full_cmd)
        resp = ser.read_until(b'\r', size=150)
        ser.close()
        return resp
    except Exception as e:
        return f"Error: {e}".encode()

test_cmds = [
    'QPR', 'QSET', 'QBEV', 'QAC2V', 'QPGS0', 'QPGS1', 'QPGS2',
    'QPIGS2', 'QOPM', 'QOFF', 'QON', 'QBAT', 'QCV', 'QDV'
]

ports = {'inv3': '/dev/ttyUSB1', 'inv2': '/dev/ttyUSB2'}

for inv, p in ports.items():
    print(f'=== Testing Extended Query Commands on {inv} ({p}) ===')
    for c in test_cmds:
        resp = query_cmd(p, c)
        if resp and not resp.startswith(b'(NAK'):
            print(f'  {c:<8} -> {resp}')
        else:
            print(f'  {c:<8} -> NAK')
        time.sleep(0.15)
    print()
