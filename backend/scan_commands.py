import serial
import time
import string

def crc16(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000: crc = (crc << 1) ^ 0x1021
            else: crc = crc << 1
            crc &= 0xFFFF
    h, l = (crc >> 8) & 0xFF, crc & 0xFF
    if h in (0x0A, 0x0D, 0x28): h += 1
    if l in (0x0A, 0x0D, 0x28): l += 1
    return bytes([h, l])

def tcmd(s, cmd):
    cb = cmd.encode('ascii')
    s.reset_input_buffer()
    s.write(cb + crc16(cb) + b'\r')
    time.sleep(0.05)
    resp = s.read_until(b'\r')
    if resp and not resp.startswith(b'(NAK') and len(resp) > 2:
        print(f"{cmd} => {resp}")
        
try:
    s = serial.Serial('/dev/ttyUSB2', 2400, timeout=0.1)
    print("Testing 3-letter commands...")
    for c1 in string.ascii_uppercase:
        for c2 in string.ascii_uppercase:
            tcmd(s, f"Q{c1}{c2}")
            
    print("Testing logical daily/monthly/yearly commands...")
    prefixes = ['QG', 'QL', 'QB', 'QGI', 'QGE', 'QBC', 'QBD']
    suffixes = ['D', 'M', 'Y', 'T']
    
    for p in prefixes:
        for suf in suffixes:
            if suf == 'D': tcmd(s, f"{p}{suf}20260806")
            elif suf == 'M': tcmd(s, f"{p}{suf}202608")
            elif suf == 'Y': tcmd(s, f"{p}{suf}2026")
            elif suf == 'T': tcmd(s, f"{p}{suf}")
            
    s.close()
except Exception as e:
    print(e)
