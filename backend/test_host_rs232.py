import serial
import time
import sys

def crc16(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = (crc << 1)
            crc &= 0xFFFF
    high = (crc >> 8) & 0xFF
    low = crc & 0xFF
    if high in (0x0D, 0x0A, 0x28): high += 1
    if low in (0x0D, 0x0A, 0x28): low += 1
    return bytes([high, low])

def test_port(port, baud):
    sys.stdout.write(f"Testing {port} @ {baud} baud... ")
    sys.stdout.flush()
    try:
        ser = serial.Serial(port, baud, timeout=1.2)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        cmd = b"QPIGS" + crc16(b"QPIGS") + b"\r"
        ser.write(cmd)
        time.sleep(0.4)
        res = ser.read(256)
        ser.close()

        if res:
            sys.stdout.write(f"RESP ({len(res)} bytes): {res}\n")
            try:
                sys.stdout.write(f"  ASCII: {res.decode('ascii', errors='ignore')}\n")
            except Exception:
                pass
        else:
            sys.stdout.write("NO RESPONSE (0 bytes)\n")
    except Exception as e:
        sys.stdout.write(f"ERROR: {e}\n")
    sys.stdout.flush()

if __name__ == "__main__":
    print("=== RS232 SERIAL INVERTER PROBE ===", flush=True)
    for p in ["/dev/ttyUSB0", "/dev/ttyUSB1"]:
        for b in [2400, 9600, 19200]:
            test_port(p, b)
