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

def read_modbus_telemetry(port="/dev/ttyUSB0", baud=9600, slave_id=1):
    print(f"Reading Modbus telemetry on {port} @ {baud} baud (Slave {slave_id})...", flush=True)
    try:
        ser = serial.Serial(port, baud, timeout=1.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Read 20 Holding Registers starting at 0
        pdu = bytes([slave_id, 0x03, 0x00, 0x00, 0x00, 0x14])
        req = pdu + modbus_crc16(pdu)
        ser.write(req)
        time.sleep(0.3)
        res = ser.read(256)
        ser.close()

        if res and len(res) >= 5 and res[0] == slave_id:
            byte_cnt = res[2]
            regs = []
            for k in range(0, byte_cnt, 2):
                val = (res[3+k] << 8) | res[4+k]
                regs.append(val)
            print(f"[SUCCESS] Received {len(regs)} registers:", flush=True)
            for idx, val in enumerate(regs):
                print(f"  Reg {idx:2d} (0x{idx:02X}): {val} (0x{val:04X})", flush=True)
            return regs
        else:
            print(f"[NO MATCH] Response bytes: {res.hex() if res else 'EMPTY'}", flush=True)
            return None
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
        return None

if __name__ == "__main__":
    read_modbus_telemetry("/dev/ttyUSB0", 9600, 1)
