import serial
import time
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
    if resp and not resp.startswith(b'(NAK'):
        print(f"{cmd} => {resp}")

try:
    s = serial.Serial('/dev/ttyUSB2', 2400, timeout=0.1)
    cmds = ['QCD20260806', 'QFD20260806', 'QDD20260806', 'QBD20260806', 'QTD20260806', 'QOD20260806', 'QXD20260806', 'QYD20260806', 'QZD20260806', 'QCT', 'QFT', 'QDT']
    for c in cmds: tcmd(s, c)
    s.close()
except Exception as e:
    print(e)
