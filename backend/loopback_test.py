import serial
import time
import sys

def loopback_test():
    print("--- LOOPBACK TEST RUNNING ON /dev/ttyUSB1 ---")
    print("Touch two bare wires together. If they are TX and RX, you will see 'LOOPBACK SUCCESS!'")
    try:
        ser = serial.Serial("/dev/ttyUSB1", 9600, timeout=0.5)
        while True:
            ser.reset_input_buffer()
            ser.write(b"HELLO\n")
            time.sleep(0.2)
            res = ser.read(1024)
            if b"HELLO" in res:
                print("LOOPBACK SUCCESS! You found TX and RX!")
            else:
                print(".", end="", flush=True)
            time.sleep(0.5)
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    loopback_test()
