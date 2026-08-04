import serial
import glob
import time

def crc16_voltronic(command: str) -> bytes:
    crc = 0x0000
    for char in command:
        crc = crc ^ (ord(char) << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return bytes([crc >> 8, crc & 0xFF])

def main():
    ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyUSB3"]
    print("=== FAST PROBE OF ALL 4 SERIAL PORTS ===", flush=True)

    qpigs = b"QPIGS" + crc16_voltronic("QPIGS") + b"\r"
    mb1 = b"\x01\x03\x00\x00\x00\x05\x85\xc9"

    for p in ports:
        for baud in [2400, 9600]:
            try:
                ser = serial.Serial(p, baud, timeout=0.2)
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                # Test Voltronic QPIGS
                ser.write(qpigs)
                time.sleep(0.1)
                r_q = ser.read(128)
                if r_q and any(b != 0 for b in r_q):
                    print(f"[{p} @ {baud}] QPIGS ({len(r_q)}b): {r_q.hex()}", flush=True)

                # Test Modbus RTU Slave 1
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.write(mb1)
                time.sleep(0.1)
                r_m = ser.read(128)
                if r_m and any(b != 0 for b in r_m):
                    print(f"[{p} @ {baud}] Modbus ({len(r_m)}b): {r_m.hex()}", flush=True)

                ser.close()
            except Exception as e:
                pass

if __name__ == "__main__":
    main()
