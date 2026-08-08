import serial, time
from serial_reader import crc16_voltronic

cmds = {
    'Solar': 'QET',
    'Load': 'QLT',
    'Grid Import': 'QGT',
    'Grid Export': 'QDT',
    'Battery Charge': 'QCT',
    'Battery Discharge': 'QFT'
}

for port, inv_name in [('/dev/ttyUSB1', 'Inverter 2'), ('/dev/ttyUSB2', 'Inverter 1')]:
    print(f"\n--- {inv_name} ({port}) ---")
    ser = serial.Serial(port, 2400, timeout=1.0)
    for name, cmd in cmds.items():
        cb = cmd.encode('ascii')
        full = cb + crc16_voltronic(cb) + b'\r'
        ser.reset_input_buffer()
        ser.write(full)
        try:
            resp = ser.read_until(b'\r', size=50)
            # Response is typically like b'(0000278700[crc]\r'
            resp_str = resp.decode('ascii', errors='ignore')
            if resp_str.startswith('('):
                # Extract digits
                val_str = ''.join(c for c in resp_str if c.isdigit())
                if val_str:
                    wh = int(val_str)
                    print(f"{name:<18}: {wh/1000.0} kWh (Raw: {resp})")
                else:
                    print(f"{name:<18}: NO DIGITS (Raw: {resp})")
            else:
                print(f"{name:<18}: UNEXPECTED FORMAT (Raw: {resp})")
        except Exception as e:
            print(f"{name:<18}: Error: {e}")
        time.sleep(0.3)
    ser.close()
