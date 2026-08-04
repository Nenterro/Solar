import serial
import time

def test_qpigs(port="/dev/ttyUSB0", baud=2400):
    try:
        ser = serial.Serial(port, baud, timeout=1.0)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Voltronic QPIGS command with CRC16
        cmd = b"QPIGS\xb7\xa9\r"
        ser.write(cmd)
        time.sleep(0.3)
        resp = ser.read(256)
        print(f"=== RAW READ FROM {port} @ {baud} BAUD ===")
        print("HEX:", resp.hex())
        print("ASCII:", resp.decode('ascii', errors='ignore'))
        ser.close()
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    test_qpigs("/dev/ttyUSB0", 2400)
