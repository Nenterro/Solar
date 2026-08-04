import serial
import glob
import time
import struct

def main():
    ports = sorted(glob.glob("/dev/ttyUSB*"))
    print(f"=== CHECKING ALL CONNECTED PORTS: {ports} ===", flush=True)

    for p in ports:
        print(f"\n==========================================", flush=True)
        print(f"PORT: {p}", flush=True)
        print(f"==========================================", flush=True)

        for baud in [2400, 9600, 19200]:
            for rts in [True, False]:
                try:
                    ser = serial.Serial(p, baud, timeout=0.3)
                    ser.rts = rts
                    ser.dtr = not rts
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()

                    # Query 1: b"QPIGS\r"
                    ser.write(b"QPIGS\r")
                    time.sleep(0.15)
                    r1 = ser.read(256)
                    if r1 and any(b != 0 for b in r1):
                        print(f"  [FOUND {p} @ {baud} RTS={rts}] QPIGS ({len(r1)}b): {r1.hex()}", flush=True)
                        for k in range(0, len(r1)-3):
                            if r1[k] in (0x41, 0x42, 0x43, 0x44, 0x45):
                                try:
                                    fv = struct.unpack('>f', r1[k:k+4])[0]
                                    if 100.0 <= fv <= 25000.0:
                                        print(f"    --> FLOAT VALUE DECODED: {fv:.2f} W ({fv/1000.0:.2f} kW)", flush=True)
                                except Exception:
                                    pass

                    # Query 2: Modbus Slave 1
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    ser.write(b"\x01\x03\x00\x00\x00\x0a\xc5\xcd")
                    time.sleep(0.15)
                    r2 = ser.read(256)
                    if r2 and any(b != 0 for b in r2):
                        print(f"  [FOUND {p} @ {baud} RTS={rts}] Modbus S1 ({len(r2)}b): {r2.hex()}", flush=True)

                    ser.close()
                except Exception:
                    pass

if __name__ == "__main__":
    main()
