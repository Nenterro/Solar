import serial
import glob
import time

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
    print(f"=== TESTING QPIGS ON {port} ACROSS ALL BAUD RATES ===", flush=True)

    cmd = "QPIGS"
    crc = crc16_voltronic(cmd)
    payload = cmd.encode('ascii') + crc + b'\r'

    for baud in [2400, 4800, 9600, 19200, 38400, 57600, 115200]:
        for rts in [True, False]:
            for dtr in [True, False]:
                try:
                    ser = serial.Serial(port, baud, timeout=0.8)
                    ser.rts = rts
                    ser.dtr = dtr
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()

                    ser.write(payload)
                    time.sleep(0.2)
                    res = ser.read(256)

                    if res:
                        print(f"[SUCCESS @ {baud} baud RTS={rts} DTR={dtr}] RAW ({len(res)}b): {res}", flush=True)
                        if b'(' in res:
                            print(f"  ASCII DECODED: {res.decode('ascii', errors='ignore')}", flush=True)
                        else:
                            print(f"  HEX: {res.hex()}", flush=True)
                    ser.close()
                except Exception as e:
                    pass

if __name__ == "__main__":
    main()
