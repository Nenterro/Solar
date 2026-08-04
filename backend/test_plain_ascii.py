import serial
import time

def test_cmd(ser, cmd_bytes, label):
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(cmd_bytes)
    time.sleep(0.3)
    resp = ser.read(256)
    print(f"\n--- [{label}] Sent: {cmd_bytes} ---")
    print("RAW BYTES:", resp)
    if resp:
        print("HEX:", resp.hex())
        try:
            ascii_str = resp.decode('ascii', errors='ignore')
            print("ASCII STRING:", ascii_str)
        except Exception:
            pass

def main():
    port = "/dev/ttyUSB0"
    print(f"=== TESTING PLAIN ASCII COMMANDS (NO CRC) ON {port} ===", flush=True)

    ser = serial.Serial(port, 2400, timeout=1.0)

    test_cmd(ser, b"QPIGS\r", "QPIGS")
    test_cmd(ser, b"QPGS0\r", "QPGS0")
    test_cmd(ser, b"QPGS1\r", "QPGS1")
    test_cmd(ser, b"QPGS2\r", "QPGS2")
    test_cmd(ser, b"QID\r", "QID")
    test_cmd(ser, b"QPI\r", "QPI")
    test_cmd(ser, b"QMD\r", "QMD")

    ser.close()

if __name__ == "__main__":
    main()
