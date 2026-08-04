import serial
import glob
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
    ports = ["/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyUSB3"]
    print(f"=== TESTING FTDI PORTS: {ports} ===", flush=True)

    qpigs = b"QPIGS\xb7\xa9\r"
    mb1 = b"\x01\x03\x00\x00\x00\x05\x85\xc9"
    mb2 = b"\x02\x03\x00\x00\x00\x05\x85\xfa"

    for p in ports:
        print(f"\n--- PROBING FTDI PORT: {p} ---", flush=True)
        for baud in [2400, 9600, 19200, 38400, 115200]:
            for parity in [serial.PARITY_NONE, serial.PARITY_EVEN]:
                for rts in [True, False]:
                    try:
                        ser = serial.Serial(p, baud, parity=parity, timeout=0.3)
                        ser.rts = rts
                        ser.dtr = not rts
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()

                        # Try QPIGS
                        ser.write(qpigs)
                        time.sleep(0.1)
                        res_q = ser.read(128)
                        if res_q and any(b != 0 for b in res_q):
                            print(f"  [SUCCESS {p} @ {baud} P={parity} RTS={rts}] QPIGS ({len(res_q)}b): {res_q.hex()}", flush=True)

                        # Try Modbus Slave 1
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()
                        ser.write(mb1)
                        time.sleep(0.1)
                        res_m1 = ser.read(128)
                        if res_m1 and any(b != 0 for b in res_m1):
                            print(f"  [SUCCESS {p} @ {baud} P={parity} RTS={rts}] Modbus S1 ({len(res_m1)}b): {res_m1.hex()}", flush=True)

                        # Try Modbus Slave 2
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()
                        ser.write(mb2)
                        time.sleep(0.1)
                        res_m2 = ser.read(128)
                        if res_m2 and any(b != 0 for b in res_m2):
                            print(f"  [SUCCESS {p} @ {baud} P={parity} RTS={rts}] Modbus S2 ({len(res_m2)}b): {res_m2.hex()}", flush=True)

                        ser.close()
                    except Exception:
                        pass

if __name__ == "__main__":
    main()
