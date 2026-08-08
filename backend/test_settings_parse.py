import serial, time, re

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

def query_cmd(port, cmd):
    try:
        ser = serial.Serial(port, 2400, timeout=1.5)
        cb = cmd.encode('ascii')
        full_cmd = cb + crc16_voltronic(cb) + b'\r'
        ser.reset_input_buffer()
        ser.write(full_cmd)
        resp = ser.read_until(b'\r', size=150)
        ser.close()
        return resp.decode('ascii', errors='ignore').strip()
    except Exception as e:
        return f"Error: {e}"

def parse_settings(qpiri_str, qflag_str):
    settings = {}
    
    # Parse QPIRI fields
    # Example: (230.0 43.4 230.0 50.0 43.4 10000 10000 48.0 52.0 46.0 57.6 57.2 2 030 040 0 1 1 6 ...
    if qpiri_str.startswith('('):
        parts = qpiri_str[1:].split()
        if len(parts) >= 18:
            output_priority_code = parts[16] # 0 = Utility, 1 = Solar, 2 = SBU, 3 = SUB
            charger_priority_code = parts[17] # 0 = Utility, 1 = Solar, 2 = Solar & Utility, 3 = Only Solar
            
            output_map = {'0': 'Utility First (USB)', '1': 'Solar First (SUB)', '2': 'SBU Priority', '3': 'SUB Priority'}
            charger_map = {'0': 'Utility First', '1': 'Solar First', '2': 'Solar & Utility (SNU)', '3': 'Only Solar (OSO)'}
            
            settings['output_source_priority'] = {
                'raw': output_priority_code,
                'description': output_map.get(output_priority_code, f'Unknown ({output_priority_code})')
            }
            settings['charging_source_priority'] = {
                'raw': charger_priority_code,
                'description': charger_map.get(charger_priority_code, f'Unknown ({charger_priority_code})')
            }

    # Parse QFLAG for Feed to Grid (flag 'b')
    # Example: (EabdkuxyzDijlnv
    if qflag_str.startswith('('):
        e_part = ''
        d_part = ''
        if 'D' in qflag_str:
            parts = qflag_str[1:].split('D')
            e_part = parts[0]
            d_part = parts[1] if len(parts) > 1 else ''
        else:
            e_part = qflag_str[1:]

        feed_to_grid_enabled = 'b' in e_part
        settings['feed_to_grid'] = {
            'enabled': feed_to_grid_enabled,
            'description': 'Enabled (Grid Export Allowed)' if feed_to_grid_enabled else 'Disabled (No Grid Export)'
        }
        
    return settings

ports = {'inv3': '/dev/ttyUSB1', 'inv2': '/dev/ttyUSB2'}

for inv, p in ports.items():
    qpiri = query_cmd(p, 'QPIRI')
    qflag = query_cmd(p, 'QFLAG')
    parsed = parse_settings(qpiri, qflag)
    print(f'=== Settings for {inv} ===')
    print('Raw QPIRI:', qpiri)
    print('Raw QFLAG:', qflag)
    print('Parsed Settings:', parsed)
    print()
