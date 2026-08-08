import serial
import time
import glob

def crc16_voltronic(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    crc_high = (crc >> 8) & 0xFF
    crc_low = crc & 0xFF
    if crc_high in (0x0A, 0x0D, 0x28): crc_high += 1
    if crc_low in (0x0A, 0x0D, 0x28): crc_low += 1
    return bytes([crc_high, crc_low])

def test_cmd(s, cmd_str):
    cmd_bytes = cmd_str.encode('ascii')
    full_cmd = cmd_bytes + crc16_voltronic(cmd_bytes) + b'\r'
    s.reset_input_buffer()
    s.write(full_cmd)
    time.sleep(0.5)
    resp = s.read_until(b'\r')
    print(f'  {cmd_str}: {resp}')

ports = glob.glob('/dev/ttyUSB*')
for p in ports:
    print(f'Testing {p}...')
    try:
        s = serial.Serial(p, 2400, timeout=1.0)
        test_cmd(s, 'QET')
        test_cmd(s, 'QED20260806')
        test_cmd(s, 'QEM202608')
        test_cmd(s, 'QEY2026')
        test_cmd(s, 'QPI')
        s.close()
    except Exception as e:
        print(f'  Error: {e}')
