import serial
import time

def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return bytes([crc & 0xFF, crc >> 8])

def read_registers(ser, start, count):
    req_body = bytes([1, 0x03, (start >> 8) & 0xFF, start & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
    req = req_body + crc16_modbus(req_body)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(req)
    time.sleep(0.3)
    resp = ser.read(1024)
    if resp and len(resp) >= 5 and resp[0] == 1 and resp[1] == 0x03:
        b_cnt = resp[2]
        regs = []
        for i in range(0, b_cnt, 2):
            if 3 + i + 1 < len(resp):
                val = (resp[3+i] << 8) | resp[4+i]
                regs.append(val)
        return regs
    return None

def main():
    print("=== SCANNING MODBUS REGS AT 9600 BAUD ===")
    ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1.0)
    for block in range(0, 200, 10):
        regs = read_registers(ser, block, 10)
        if regs:
            has_data = any(r > 0 for r in regs)
            if has_data:
                print(f"REGS {block}-{block+9}: {regs}")
                for i, v in enumerate(regs):
                    if v > 0:
                        print(f"  Reg {block+i}: {v} (0x{v:04X})")
    ser.close()

if __name__ == "__main__":
    main()
