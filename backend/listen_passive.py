import serial
import time

def main():
    print("--- PASSIVE LISTEN AT 9600 BAUD FOR 15 SECONDS ---")
    try:
        ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1.0)
        ser.reset_input_buffer()
        t_end = time.time() + 15
        while time.time() < t_end:
            res = ser.read(1024)
            if res:
                print(f"[{time.time()}] RAW:", res.hex())
        ser.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
