import serial, time, string
from serial_reader import crc16_voltronic

cmds = [f'Q{c}D20260806' for c in string.ascii_uppercase]

for port in ['/dev/ttyUSB1', '/dev/ttyUSB2']:
    print(f"--- PORT {port} ---")
    ser = serial.Serial(port, 2400, timeout=1.0)
    for cmd in cmds:
        if cmd in ['QED20260806', 'QLD20260806', 'QGD20260806', 'QFD20260806', 'QCD20260806']:
            continue
        cb = cmd.encode('ascii')
        full = cb + crc16_voltronic(cb) + b'\r'
        ser.reset_input_buffer()
        ser.write(full)
        try:
            resp = ser.read_until(b'\r', size=50)
            if b'NAK' not in resp and len(resp) > 3:
                print(f"FOUND MATCH: {cmd} -> {resp}")
        except Exception as e:
            print(f"Error on {cmd}: {e}")
        time.sleep(0.2)
    ser.close()
