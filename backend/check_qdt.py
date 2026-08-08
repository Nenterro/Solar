import serial, time
from serial_reader import crc16_voltronic

cmd = 'QDT'
cb = cmd.encode('ascii')
full = cb + crc16_voltronic(cb) + b'\r'
ser = serial.Serial('/dev/ttyUSB2', 2400, timeout=1.0)
ser.reset_input_buffer()
ser.write(full)
try:
    resp = ser.read_until(b'\r', size=50)
    print(f"{cmd} -> {resp}")
except Exception as e:
    print(f"Error: {e}")
ser.close()
