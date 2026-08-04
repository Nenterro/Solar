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

def main():
    port = "/dev/ttyUSB0"
    print(f"=== SCANNING MODBUS REGISTERS @ 2400 BAUD ON {port} ===", flush=True)

    ser = serial.Serial(port, 2400, timeout=0.8)

    # Send 10-register reads across start registers 0, 10, 20, 30, 40, 50
    for start in [0, 10, 20, 30, 40, 50]:
        mb_req = bytes([1, 0x03, (start >> 8) & 0xFF, start & 0xFF, 0x00, 0x0A])
        mb_payload = mb_req + crc16_modbus(mb_req)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(mb_payload)
        time.sleep(0.3)
        res = ser.read(256)
        if res and len(res) >= 5 and res[0] == 1 and res[1] == 0x03:
            byte_cnt = res[2]
            regs = []
            for k in range(0, byte_cnt, 2):
                if 3 + k + 1 < len(res):
                    val = (res[3+k] << 8) | res[4+k]
                    regs.append(val)
            print(f"[START REG {start:02d}] ({len(regs)} regs): {regs}")
            for idx, v in enumerate(regs):
                r_num = start + idx
                print(f"  Reg {r_num:02d} (0x{r_num:02X}): Decimal {v} | Hex 0x{v:04X}")

    ser.close()

if __name__ == "__main__":
    main()
