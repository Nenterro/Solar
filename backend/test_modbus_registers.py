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

def read_holding(ser, slave_id, start_reg, count):
    pdu = bytes([slave_id, 0x03, (start_reg >> 8) & 0xFF, start_reg & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
    req = pdu + modbus_crc16(pdu)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(req)
    time.sleep(0.3)
    resp = ser.read(256)
    return resp

def read_input(ser, slave_id, start_reg, count):
    pdu = bytes([slave_id, 0x04, (start_reg >> 8) & 0xFF, start_reg & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
    req = pdu + modbus_crc16(pdu)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(req)
    time.sleep(0.3)
    resp = ser.read(256)
    return resp

def main():
    port = "/dev/ttyUSB0"
    print(f"==================================================", flush=True)
    print(f"TESTING MODBUS RTU REGISTERS ON {port}", flush=True)
    print(f"==================================================", flush=True)

    for baud in [9600, 2400, 19200]:
        print(f"\n--- Testing Baud: {baud} ---", flush=True)
        try:
            ser = serial.Serial(port, baud, timeout=1.0)
            
            for slave_id in [1, 2, 3, 4, 5, 247]:
                # Try Holding Registers 0..20
                res = read_holding(ser, slave_id, 0, 20)
                if res and len(res) >= 5 and res[0] == slave_id and res[1] == 0x03:
                    print(f"  [SUCCESS] Slave {slave_id} Baud {baud} Func 0x03 -> LEN {len(res)} HEX: {res.hex()}", flush=True)
                    # Decode 16-bit registers
                    byte_cnt = res[2]
                    regs = []
                    for k in range(0, byte_cnt, 2):
                        val = (res[3+k] << 8) | res[4+k]
                        regs.append(val)
                    print(f"    Registers 0..{len(regs)-1}: {regs}", flush=True)

                # Try Input Registers 0..20
                res_in = read_input(ser, slave_id, 0, 20)
                if res_in and len(res_in) >= 5 and res_in[0] == slave_id and res_in[1] == 0x04:
                    print(f"  [SUCCESS] Slave {slave_id} Baud {baud} Func 0x04 -> LEN {len(res_in)} HEX: {res_in.hex()}", flush=True)
                    byte_cnt = res_in[2]
                    regs = []
                    for k in range(0, byte_cnt, 2):
                        val = (res_in[3+k] << 8) | res_in[4+k]
                        regs.append(val)
                    print(f"    Input Regs 0..{len(regs)-1}: {regs}", flush=True)

            ser.close()
        except Exception as e:
            print(f"  Error at {baud} baud: {e}", flush=True)

if __name__ == "__main__":
    main()
