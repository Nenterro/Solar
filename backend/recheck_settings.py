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

ports = {'inv3': '/dev/ttyUSB1', 'inv2': '/dev/ttyUSB2'}

out_map = {'0': 'Utility First (USB)', '1': 'Solar First (SUB)', '2': 'SBU Priority', '3': 'SUB Priority'}
charger_map = {'0': 'Utility First (CSO)', '1': 'Solar First (CSI)', '2': 'Solar & Utility (SNU)', '3': 'Only Solar (OSO)'}

for inv, p in ports.items():
    qpiri = query_cmd(p, 'QPIRI')
    qflag = query_cmd(p, 'QFLAG')
    print(f'=== Live Hardware Query: {inv} ({p}) ===')
    print('Raw QPIRI:', qpiri)
    print('Raw QFLAG:', qflag)
    
    if qpiri.startswith('('):
        parts = qpiri[1:].split()
        if len(parts) >= 18:
            mach = parts[12]
            out_code = parts[16]
            chg_code = parts[17]
            max_chg_curr = parts[13] if len(parts) >= 14 else 'N/A'
            max_ac_chg_curr = parts[14] if len(parts) >= 15 else 'N/A'
            
            e_part, d_part = '', ''
            if 'D' in qflag:
                sp = qflag[1:].split('D')
                e_part = sp[0]
                d_part = sp[1] if len(sp) > 1 else ''
            else:
                e_part = qflag[1:]
                
            flag_d_enabled = 'd' in e_part
            
            print(f'  • Machine Type: {mach} (Hybrid Grid-Tie with Backup)')
            print(f'  • Output Source Priority: {out_code} -> {out_map.get(out_code, "Unknown")}')
            print(f'  • Charging Source Priority: {chg_code} -> {charger_map.get(chg_code, "Unknown")}')
            print(f'  • Max Charging Current: {max_chg_curr} A')
            print(f'  • Max Utility (AC) Charging Current: {max_ac_chg_curr} A')
            print(f'  • Solar Feed to Grid (Flag d): {"ENABLED" if flag_d_enabled else "DISABLED"}')
    print()
