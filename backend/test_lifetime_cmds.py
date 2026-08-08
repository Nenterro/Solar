import serial, time
from serial_reader import crc16_voltronic

cmds = ['QET', 'QLT', 'QGT', 'QFD', 'QFT', 'QCD', 'QCT', 'QDD']

for port in ['/dev/ttyUSB1', '/dev/ttyUSB2']:
    print(f"\n=================== {port} ===================")
    try:
        s = serial.Serial(port, 2400, timeout=1.5)
        for cmd in cmds:
            b_cmd = cmd.encode('ascii')
            full_cmd = b_cmd + crc16_voltronic(b_cmd) + b'\r'
            s.reset_input_buffer()
            s.write(full_cmd)
            r = s.read_until(b'\r', size=50)
            print(f"{cmd:<5}: {r}")
            time.sleep(0.15)
        s.close()
    except Exception as e:
        print(f"Error on {port}: {e}")
