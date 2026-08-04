import serial
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
    port = "/dev/ttyUSB0"
    print(f"=== TESTING QPIGS VARIANTS ON {port} ===", flush=True)

    ser = serial.Serial(port, 2400, timeout=1.0)

    # Variant 1: Plain "QPIGS\r"
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    v1 = b"QPIGS\r"
    ser.write(v1)
    time.sleep(0.3)
    r1 = ser.read(256)
    print("\n[VARIANT 1: Plain QPIGS\\r]:")
    print("  RAW:", r1)
    if r1:
        print("  HEX:", r1.hex())
        print("  ASCII:", r1.decode('ascii', errors='ignore'))

    # Variant 2: "QPIGS" + Voltronic CRC + "\r"
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    crc = crc16_voltronic("QPIGS")
    v2 = b"QPIGS" + crc + b"\r"
    ser.write(v2)
    time.sleep(0.3)
    r2 = ser.read(256)
    print("\n[VARIANT 2: QPIGS + CRC + \\r]:")
    print("  RAW:", r2)
    if r2:
        print("  HEX:", r2.hex())
        print("  ASCII:", r2.decode('ascii', errors='ignore'))

    # Variant 3: "QPGS0\r" (Parallel Inverter 1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    crc_p0 = crc16_voltronic("QPGS0")
    v3 = b"QPGS0" + crc_p0 + b"\r"
    ser.write(v3)
    time.sleep(0.3)
    r3 = ser.read(256)
    print("\n[VARIANT 3: QPGS0 + CRC + \\r]:")
    print("  RAW:", r3)
    if r3:
        print("  HEX:", r3.hex())
        print("  ASCII:", r3.decode('ascii', errors='ignore'))

    ser.close()

if __name__ == "__main__":
    main()
