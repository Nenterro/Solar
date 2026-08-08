import serial, time
from serial_reader import crc16_voltronic

cmd_qpigs = b'QPIGS' + crc16_voltronic(b'QPIGS') + b'\r'
cmd_qpigs2 = b'QPIGS2' + crc16_voltronic(b'QPIGS2') + b'\r'

for port in ['/dev/ttyUSB1', '/dev/ttyUSB2']:
    print(f"\n=== {port} ===")
    try:
        s = serial.Serial(port, 2400, timeout=1.5)
        s.reset_input_buffer()
        s.write(cmd_qpigs)
        r1 = s.read_until(b'\r', size=150)
        print(f"QPIGS : {r1}")
        
        time.sleep(0.2)
        s.reset_input_buffer()
        s.write(cmd_qpigs2)
        r2 = s.read_until(b'\r', size=150)
        print(f"QPIGS2: {r2}")
        s.close()
    except Exception as e:
        print(f"Error: {e}")
