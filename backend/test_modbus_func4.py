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

def read_modbus_func4(ser, slave: int, start_reg: int, qty: int):
    req_body = bytes([slave, 0x04, (start_reg >> 8) & 0xFF, start_reg & 0xFF, (qty >> 8) & 0xFF, qty & 0xFF])
    req = req_body + crc16_modbus(req_body)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(req)
    time.sleep(0.2)
    res = ser.read(256)
    if res and len(res) >= 5 and res[0] == slave and res[1] == 0x04:
        byte_cnt = res[2]
        regs = []
        for k in range(0, byte_cnt, 2):
            if 3 + k + 1 < len(res):
                val = (res[3+k] << 8) | res[4+k]
                regs.append(val)
        return regs
    return None

def main():
    port = "/dev/ttyUSB0"
    print(f"=== TESTING MODBUS FUNC 4 (INPUT REGISTERS) ON {port} ===", flush=True)

    for baud in [9600, 2400]:
        try:
            ser = serial.Serial(port, baud, timeout=0.8)
            for slave in [1, 2, 3]:
                for base in [0x0000, 0x0100, 0x0200, 0x0300, 0x0500, 0x0600, 0x0A00, 0x1000]:
                    regs = read_modbus_func4(ser, slave, base, 10)
                    if regs and any(r > 0 for r in regs):
                        print(f"[SUCCESS Baud {baud} Slave {slave} Base 0x{base:04X}] Regs: {regs}", flush=True)
            ser.close()
        except Exception as e:
            print(f"Error @ {baud}: {e}", flush=True)

if __name__ == "__main__":
    main()
