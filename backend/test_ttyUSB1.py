import serial
import time

def test_port():
    print("--- POLLING /dev/ttyUSB1 FOR QPIGS ---")
    cmd = b"QPIGS\xb7\xa9\r"
    try:
        ser = serial.Serial("/dev/ttyUSB1", 2400, timeout=1.0)
        ser.reset_input_buffer()
        ser.write(cmd)
        time.sleep(0.5)
        res = ser.read(1024)
        if res:
            print(f"SUCCESS! RAW:", res.hex())
            print(f"ASCII:", res.decode('ascii', errors='ignore'))
        else:
            print("NO RESPONSE.")
        ser.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_port()
