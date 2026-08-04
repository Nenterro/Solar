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

def make_modbus_req(slave_id: int, func: int, start_reg: int, count: int) -> bytes:
    pdu = bytes([slave_id, func, (start_reg >> 8) & 0xFF, start_reg & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
    return pdu + modbus_crc16(pdu)

def test_port(port):
    print(f"\n==========================================", flush=True)
    print(f"DEEP PROBE ON PORT: {port}", flush=True)
    print(f"==========================================", flush=True)
    
    for baud in [2400, 9600, 19200, 115200]:
        try:
            ser = serial.Serial(port, baud, timeout=1.0)
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # 1. Voltronic ASCII commands (with & without CRC)
            for cmd_str in ["QPIGS", "QID", "QPGS0", "QPI"]:
                # Voltronic CRC
                crc_val = 0x0000
                for b in cmd_str.encode('ascii'):
                    crc_val ^= (b << 8)
                    for _ in range(8):
                        if crc_val & 0x8000: crc_val = (crc_val << 1) ^ 0x1021
                        else: crc_val <<= 1
                        crc_val &= 0xFFFF
                h, l = (crc_val >> 8) & 0xFF, crc_val & 0xFF
                if h in (0x0D, 0x0A, 0x28): h += 1
                if l in (0x0D, 0x0A, 0x28): l += 1
                
                v_cmd = cmd_str.encode('ascii') + bytes([h, l]) + b'\r'
                ser.write(v_cmd)
                time.sleep(0.2)
                res = ser.read(256)
                if res and res != b'\x00' * len(res):
                    print(f"  [FOUND VOLTRONIC @ {baud}] {port} CMD {cmd_str} -> RAW ({len(res)}b): {res}")
                    print(f"    ASCII: {res.decode('ascii', errors='ignore')}")

            # 2. Modbus RTU commands (Func 0x03 & 0x04 for Slaves 1..3)
            for slave_id in [1, 2, 3]:
                for func in [3, 4]:
                    req = make_modbus_req(slave_id, func, 0, 10)
                    ser.write(req)
                    time.sleep(0.2)
                    m_res = ser.read(256)
                    if m_res and m_res != b'\x00' * len(m_res):
                        print(f"  [FOUND MODBUS RTU @ {baud}] {port} Slave {slave_id} Func {func} -> RAW ({len(m_res)}b): {m_res.hex()}")

            ser.close()
        except Exception as e:
            print(f"  Error on {port} @ {baud}: {e}")

if __name__ == "__main__":
    for p in ["/dev/ttyUSB0", "/dev/ttyUSB1"]:
        test_port(p)
