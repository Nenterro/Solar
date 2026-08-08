import serial
import time

def listen(baud):
    print(f"\n--- LISTENING AT {baud} BAUD ---")
    try:
        ser = serial.Serial('/dev/ttyUSB1', baud, timeout=1.0)
        t_end = time.time() + 4
        while time.time() < t_end:
            # We also send a QPIGS to see if it responds to polling, 
            # or if it's just continuously streaming.
            ser.write(b"QPIGS\r")
            time.sleep(0.3)
            res = ser.read(1024)
            if res:
                print(f"RAW {baud}:", res.hex())
        ser.close()
    except Exception as e:
        print(f"Error {baud}:", e)

if __name__ == "__main__":
    listen(2400)
    listen(9600)
    listen(19200)
