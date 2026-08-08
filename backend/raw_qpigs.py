import serial, time
from serial_reader import crc16_voltronic

cmd = b'QPIGS'
cmd = cmd + crc16_voltronic(cmd) + b'\r'

for port in ['/dev/ttyUSB1', '/dev/ttyUSB2']:
    print(f"=== {port} ===")
    try:
        s = serial.Serial(port, 2400, timeout=1.5)
        s.reset_input_buffer()
        s.write(cmd)
        resp = s.read_until(b'\r', size=150)
        print(f"Raw: {resp}")
        decoded = resp.decode('ascii', errors='ignore').strip()
        parts = decoded[1:].split()
        for idx, p in enumerate(parts):
            print(f"  Field {idx:02d}: {p}")
        s.close()
    except Exception as e:
        print(f"Error: {e}")
