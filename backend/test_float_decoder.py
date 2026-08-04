import serial
import struct
import time

def main():
    try:
        ser = serial.Serial("/dev/ttyUSB0", 2400, timeout=1.0)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        cmd = b"QPIGS\xb7\xa9\r"
        ser.write(cmd)
        time.sleep(0.3)
        resp = ser.read(256)

        print("RAW RESPONSE HEX:", resp.hex())

        # Read float32 chunks (4 bytes each)
        floats = []
        for i in range(0, len(resp) - 3, 4):
            chunk = resp[i:i+4]
            try:
                val = struct.unpack('>f', chunk)[0]
                if -10000.0 < val < 50000.0:
                    floats.append((i, chunk.hex(), round(val, 2)))
            except Exception:
                pass

        print("\nDECODED IEEE 754 FLOATS:")
        for idx, hex_str, val in floats:
            print(f"  Offset {idx:02d} ({hex_str}): {val}")

        ser.close()
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    main()
