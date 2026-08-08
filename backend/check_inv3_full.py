import serial, time
from serial_reader import crc16_voltronic

cmds = {
    'QID': 'QID',
    'Solar': 'QET',
    'Load': 'QLT',
    'Grid Import': 'QGT',
    'Grid Export': 'QDT',
    'Battery Charge': 'QCT',
    'Battery Discharge': 'QFT'
}

port = '/dev/ttyUSB3'
print(f"\n--- {port} ---")
try:
    ser = serial.Serial(port, 2400, timeout=1.5)
    for name, cmd in cmds.items():
        cb = cmd.encode('ascii')
        full = cb + crc16_voltronic(cb) + b'\r'
        ser.reset_input_buffer()
        ser.write(full)
        resp = ser.read_until(b'\r', size=50)
        
        resp_str = resp.decode('ascii', errors='ignore')
        if resp_str.startswith('('):
            val_str = ''.join(c for c in resp_str if c.isdigit())
            if val_str and name != 'QID':
                wh = int(val_str)
                print(f"{name:<18}: {wh/1000.0} kWh (Raw: {resp})")
            else:
                print(f"{name:<18}: {resp_str} (Raw: {resp})")
        else:
            print(f"{name:<18}: UNEXPECTED FORMAT (Raw: {resp})")
        time.sleep(0.3)
    ser.close()
except Exception as e:
    print(f"Error: {e}")
