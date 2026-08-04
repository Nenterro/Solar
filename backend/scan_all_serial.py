import serial
import glob
import time
import sys

def crc16(command: str) -> bytes:
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
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    print(f"FOUND {len(ports)} SERIAL PORTS: {ports}", flush=True)

    for p in ports:
        print(f"\n==========================================", flush=True)
        print(f"PROBING PORT: {p}", flush=True)
        print(f"==========================================", flush=True)
        
        for baud in [2400, 9600, 19200]:
            try:
                ser = serial.Serial(p, baud, timeout=1.0)
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                # Test Voltronic QPIGS
                cmd = b"QPIGS" + crc16("QPIGS") + b"\r"
                ser.write(cmd)
                time.sleep(0.3)
                res = ser.read(256)
                if res and res != b'\x00' * len(res):
                    print(f"  [SUCCESS VOLTRONIC @ {baud}] {p} -> RAW ({len(res)}b): {res}", flush=True)
                    try:
                        print(f"    ASCII: {res.decode('ascii', errors='ignore')}", flush=True)
                    except Exception:
                        pass
                
                # Test Voltronic Parallel QPGS0, QPGS1, QPGS2
                for idx in range(3):
                    cmd_p = f"QPGS{idx}"
                    payload_p = cmd_p.encode('ascii') + crc16(cmd_p) + b'\r'
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    ser.write(payload_p)
                    time.sleep(0.3)
                    res_p = ser.read(256)
                    if res_p and res_p != b'\x00' * len(res_p):
                        print(f"  [SUCCESS QPGS{idx} @ {baud}] {p} -> RAW ({len(res_p)}b): {res_p}", flush=True)
                        try:
                            print(f"    ASCII: {res_p.decode('ascii', errors='ignore')}", flush=True)
                        except Exception:
                            pass

                ser.close()
            except Exception as e:
                print(f"  Error on {p} @ {baud}: {e}", flush=True)

if __name__ == "__main__":
    main()
