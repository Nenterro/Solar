import serial
import struct
import glob
import time

def calc_crc(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

req = bytearray(struct.pack('>BBHH', 1, 3, 50, 10))
crc = calc_crc(req)
bms_cmd = req + struct.pack('<H', crc)

print("=== PROBING ALL TTYUSB PORTS ===")
for port in sorted(glob.glob('/dev/ttyUSB*')):
    print(f"\n--- Port: {port} ---")
    
    # 1. Test BMS RS485 Modbus RTU at 9600 baud
    try:
        s = serial.Serial(port, 9600, timeout=1.0)
        s.reset_input_buffer()
        s.write(bms_cmd)
        time.sleep(0.2)
        res = s.read(1024)
        s.close()
        print(f"  [BMS 9600] Read {len(res)} bytes: {res.hex() if res else 'None'}")
        if len(res) >= 20 and res[0] == 0x01 and res[1] == 0x03:
            v = struct.unpack('>H', res[4:6])[0] / 10.0
            soc = struct.unpack('>H', res[6:8])[0]
            print(f"  *** SUCCESS KNOX BMS FOUND ON {port}: SOC={soc}%, Voltage={v}V ***")
    except Exception as e:
        print(f"  [BMS] Error: {e}")

    # 2. Test Inverter QID at 2400 baud
    try:
        s = serial.Serial(port, 2400, timeout=1.0)
        s.reset_input_buffer()
        s.write(b'QID\x28\xc1\r')
        time.sleep(0.2)
        res = s.read(100)
        s.close()
        print(f"  [Inverter 2400] Read {len(res)} bytes: {res.decode('ascii', errors='ignore').strip() if res else 'None'}")
    except Exception as e:
        print(f"  [Inverter] Error: {e}")
