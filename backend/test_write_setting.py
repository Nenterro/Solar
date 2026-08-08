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

def set_setting(port, cmd):
    try:
        ser = serial.Serial(port, 2400, timeout=2.0)
        cb = cmd.encode('ascii')
        full_cmd = cb + crc16_voltronic(cb) + b'\r'
        ser.reset_input_buffer()
        ser.write(full_cmd)
        resp = ser.read_until(b'\r', size=50)
        ser.close()
        return resp
    except Exception as e:
        return f"Error: {e}".encode()

port = '/dev/ttyUSB1'
cmd = 'PBCV52.0'
print(f'Sending {cmd} to inv3 ({port})...')
resp = set_setting(port, cmd)
print('Response:', resp)
