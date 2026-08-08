import serial, time

def crc16_voltronic(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    low = crc & 0xFF
    high = (crc >> 8) & 0xFF
    if low in (0x28, 0x0D, 0x0A): low += 1
    if high in (0x28, 0x0D, 0x0A): high += 1
    return bytes([high, low])

def test_cmd(port, cmd):
    try:
        ser = serial.Serial(port, 2400, timeout=1.0)
        cb = cmd.encode('ascii')
        full_cmd = cb + crc16_voltronic(cb) + b'\r'
        ser.reset_input_buffer()
        ser.write(full_cmd)
        resp = ser.read_until(b'\r', size=150)
        ser.close()
        return resp.decode('ascii', errors='ignore').strip()
    except Exception as e:
        return f"Error: {e}"

ports = {'inv3': '/dev/ttyUSB1', 'inv2': '/dev/ttyUSB2'}

# We query QPIRI voltage fields first
for inv, p in ports.items():
    qpiri = test_cmd(p, 'QPIRI')
    if qpiri.startswith('('):
        parts = qpiri[1:].split()
        if len(parts) >= 23:
            v_back_grid = parts[8]     # Back to Grid
            v_cutoff = parts[9]        # Battery Cut-off
            v_bulk = parts[10]         # Bulk charging
            v_float = parts[11]        # Float charging
            v_back_disch = parts[22]   # Back to Discharge
            
            print(f'=== Voltage Thresholds in QPIRI for {inv} ({p}) ===')
            print(f'  1. Back to Grid Voltage (PBCV): {v_back_grid} V')
            print(f'  2. Battery Cut-Off Voltage (PSDV): {v_cutoff} V')
            print(f'  3. Back to Discharge Voltage (PBDV): {v_back_disch} V')
            print(f'  • Bulk Charge Voltage: {v_bulk} V')
            print(f'  • Float Charge Voltage: {v_float} V')
    print()
