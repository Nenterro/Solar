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
    ser = serial.Serial(port, 2400, timeout=1.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Query 10 holding registers starting at 0
    req = bytes([1, 0x03, 0x00, 0x00, 0x00, 0x0A])
    payload = req + crc16_modbus(req)
    ser.write(payload)
    time.sleep(0.4)
    res = ser.read(256)

    print("RAW BYTES READ:", res)
    if res:
        print("HEX:", res.hex())
        if len(res) >= 5:
            b_cnt = res[2]
            regs = []
            for k in range(0, b_cnt, 2):
                if 3 + k + 1 < len(res):
                    val = (res[3+k] << 8) | res[4+k]
                    regs.append(val)
            print("DECODED REGISTERS (0..9):", regs)
            for idx, r in enumerate(regs):
                print(f"  Reg {idx}: {r} (0x{r:04X})")

    ser.close()

if __name__ == "__main__":
    main()
