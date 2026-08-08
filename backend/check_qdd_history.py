import serial, time
from serial_reader import crc16_voltronic

cmds = ['QDD20260805', 'QDD20260804', 'QDD20260803', 'QDD20260802']

for port in ['/dev/ttyUSB1', '/dev/ttyUSB2']:
    ser = serial.Serial(port, 2400, timeout=1.0)
    for cmd in cmds:
        cb = cmd.encode('ascii')
        full = cb + crc16_voltronic(cb) + b'\r'
        ser.reset_input_buffer()
        ser.write(full)
        try:
            resp = ser.read_until(b'\r', size=50)
            print(f"{port}: {cmd} -> {resp}")
        except Exception as e:
            print(f"{port}: {cmd} -> Error: {e}")
        time.sleep(0.3)
    ser.close()
