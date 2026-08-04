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

def read_registers(ser, slave, start, count):
    req_body = bytes([slave, 0x03, (start >> 8) & 0xFF, start & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
    req = req_body + crc16_modbus(req_body)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(req)
    time.sleep(0.2)
    resp = ser.read(256)
    if resp and len(resp) >= 5 and resp[0] == slave and resp[1] == 0x03:
        b_cnt = resp[2]
        regs = []
        for i in range(0, b_cnt, 2):
            if 3 + i + 1 < len(resp):
                val = (resp[3+i] << 8) | resp[4+i]
                regs.append(val)
        return regs
    return None

def main():
    port = "/dev/ttyUSB0"
    print(f"=== SCANNING ALL MODBUS REGISTER BLOCKS (0..100) @ 9600 BAUD ON {port} ===", flush=True)

    ser = serial.Serial(port, 9600, timeout=0.8)

    for slave in [1, 2, 3]:
        for start in range(0, 100, 10):
            regs = read_registers(ser, slave, start, 10)
            if regs:
                print(f"[SLAVE {slave} START {start:02d}] Regs {start}-{start+9}: {regs}")
                for idx, v in enumerate(regs):
                    if v > 0:
                        print(f"   --> Reg {start+idx}: Decimal {v} | Hex 0x{v:04X} | Float32/10 {v/10.0:.1f}")

    ser.close()

if __name__ == "__main__":
    main()
