import serial, time
from serial_reader import crc16_voltronic

cmds = ['QPIGS', 'QPGS0', 'QPGS1', 'QGS', 'QPIGS2', 'QMOD', 'QPIWS']

for port in ['/dev/ttyUSB1', '/dev/ttyUSB2']:
    print(f"\n=================== {port} ===================")
    try:
        s = serial.Serial(port, 2400, timeout=1.5)
        for c in cmds:
            cb = c.encode('ascii')
            full = cb + crc16_voltronic(cb) + b'\r'
            s.reset_input_buffer()
            s.write(full)
            resp = s.read_until(b'\r', size=150)
            print(f"{c:<10}: {resp}")
            time.sleep(0.3)
        s.close()
    except Exception as e:
        print(f"Error on {port}: {e}")
