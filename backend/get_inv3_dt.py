import serial, time
from serial_reader import crc16_voltronic

cmd = b'QDT'
cmd = cmd + crc16_voltronic(cmd) + b'\r'

port = '/dev/ttyUSB1'
print(f"\n--- {port} ---")
try:
    ser = serial.Serial(port, 2400, timeout=1.5)
    ser.reset_input_buffer()
    ser.write(cmd)
    resp = ser.read_until(b'\r', size=50)
    
    resp_str = resp.decode('ascii', errors='ignore')
    if resp_str.startswith('('):
        val_str = ''.join(c for c in resp_str if c.isdigit())
        if val_str:
            wh = int(val_str)
            print(f"Battery Discharge : {wh/1000.0} kWh (Raw: {resp})")
    ser.close()
except Exception as e:
    print(f"Error: {e}")
