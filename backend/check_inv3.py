import serial, time
from serial_reader import crc16_voltronic

cmd = b'QET'
cmd = cmd + crc16_voltronic(cmd) + b'\r'

for port in ['/dev/ttyUSB0', '/dev/ttyUSB3']:
    print(f"--- {port} ---")
    try:
        s = serial.Serial(port, 2400, timeout=1.5)
        s.reset_input_buffer()
        s.write(cmd)
        resp = s.read_until(b'\r', size=50)
        print(f"Resp: {resp}")
        s.close()
    except Exception as e:
        print(f"Error: {e}")
