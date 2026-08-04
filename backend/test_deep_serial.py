import serial
import glob
import time
import sys

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
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    print(f"=== DEEP PROBE OF SERIAL PORTS: {ports} ===", flush=True)

    for p in ports:
        print(f"\n------------------------------------------", flush=True)
        print(f"PORT: {p}", flush=True)
        print(f"------------------------------------------", flush=True)
        
        for baud in [2400, 9600]:
            try:
                ser = serial.Serial(p, baud, timeout=0.5)
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                # Test 1: QPIGS
                cmd = "QPIGS"
                payload = cmd.encode('ascii') + crc16_voltronic(cmd) + b'\r'
                ser.write(payload)
                time.sleep(0.2)
                res = ser.read(256)
                if res:
                    print(f"  [BAUD {baud}] QPIGS ({len(res)}b): {res.hex()}", flush=True)

                # Test 2: QPGS0, QPGS1, QPGS2
                for idx in range(3):
                    cmd_p = f"QPGS{idx}"
                    payload_p = cmd_p.encode('ascii') + crc16_voltronic(cmd_p) + b'\r'
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    ser.write(payload_p)
                    time.sleep(0.2)
                    res_p = ser.read(256)
                    if res_p:
                        print(f"  [BAUD {baud}] QPGS{idx} ({len(res_p)}b): {res_p.hex()}", flush=True)

                # Test 3: Modbus Read Holding Registers (Slave 1, Func 3, Reg 0, Qty 10)
                mb_req = b"\x01\x03\x00\x00\x00\x0a\xc5\xcd"
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.write(mb_req)
                time.sleep(0.2)
                res_mb = ser.read(256)
                if res_mb:
                    print(f"  [BAUD {baud}] Modbus Slave 1 Reg0 ({len(res_mb)}b): {res_mb.hex()}", flush=True)

                ser.close()
            except Exception as e:
                print(f"  [BAUD {baud}] Error: {e}", flush=True)

if __name__ == "__main__":
    main()
