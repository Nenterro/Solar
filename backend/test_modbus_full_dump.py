import serial
import time
import sys

def modbus_crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 0x0001) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

def make_req(slave_id, func, start_reg, count):
    pdu = bytes([slave_id, func, (start_reg >> 8) & 0xFF, start_reg & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
    return pdu + modbus_crc16(pdu)

def dump_registers(port, baud):
    print(f"\n==========================================", flush=True)
    print(f"DUMPING MODBUS REGISTERS ON {port} @ {baud} BAUD", flush=True)
    print(f"==========================================", flush=True)

    try:
        ser = serial.Serial(port, baud, timeout=1.0)
        
        for func in [3, 4]:
            print(f"\n--- Testing Function Code 0x{func:02X} ---", flush=True)
            for start_reg in range(0, 100, 20):
                req = make_req(1, func, start_reg, 20)
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.write(req)
                time.sleep(0.2)
                res = ser.read(256)
                if res and len(res) >= 5 and res[0] == 1 and res[1] == func:
                    byte_cnt = res[2]
                    regs = []
                    for k in range(0, byte_cnt, 2):
                        val = (res[3+k] << 8) | res[4+k]
                        regs.append(val)
                    print(f"  [SUCCESS] Regs {start_reg:3d}..{start_reg+len(regs)-1:3d}: {regs}", flush=True)

        ser.close()
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    for b in [9600, 115200, 2400]:
        dump_registers("/dev/ttyUSB0", b)
