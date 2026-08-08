import serial, time
from serial_reader import crc16_voltronic

cmd = 'QDD20260806'
cb = cmd.encode('ascii')
full = cb + crc16_voltronic(cb) + b'\r'

for port in ['/dev/ttyUSB1', '/dev/ttyUSB2']:
    ser = serial.Serial(port, 2400, timeout=1.0)
    ser.reset_input_buffer()
    ser.write(full)
    try:
        resp = ser.read_until(b'\r', size=50)
        print(f"{port}: {cmd} -> {resp}")
    except Exception as e:
        print(f"{port}: Error: {e}")
    ser.close()
