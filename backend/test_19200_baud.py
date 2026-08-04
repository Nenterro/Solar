import serial
import time
import struct

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
    print(f"=== TESTING 19200 BAUD HIGH-SPEED TELEMETRY ON {port} ===", flush=True)

    ser = serial.Serial(port, 19200, timeout=1.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    cmd = "QPIGS"
    payload = cmd.encode('ascii') + crc16_voltronic(cmd) + b'\r'
    ser.write(payload)
    time.sleep(0.2)
    resp = ser.read(256)

    print("RAW RESP AT 19200 BAUD:", resp)
    print("HEX:", resp.hex())

    # Look for 16-bit register values: 0x0640 = 1600 W (1.6 kW)
    for i in range(len(resp)-1):
        w_val = (resp[i] << 8) | resp[i+1]
        if 100 <= w_val <= 25000:
            print(f"  Word Offset {i:02d}: Decimal {w_val} W ({w_val/1000.0:.2f} kW)")

    ser.close()

if __name__ == "__main__":
    main()
