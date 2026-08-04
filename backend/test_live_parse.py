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

def parse_modbus_frame(raw: bytes):
    if len(raw) < 5:
        return None
    slave_id = raw[0]
    func = raw[1]
    byte_cnt = raw[2]
    if len(raw) < 3 + byte_cnt:
        return None

    regs = []
    for k in range(0, byte_cnt, 2):
        if 3 + k + 1 < len(raw):
            val = (raw[3+k] << 8) | raw[4+k]
            regs.append(val)
    return slave_id, func, regs

def main():
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    print(f"=== PARSING LIVE SERIAL TELEMETRY FROM {ports} ===", flush=True)

    for p in ports:
        for baud in [2400, 9600]:
            try:
                ser = serial.Serial(p, baud, timeout=1.0)
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                # Test Voltronic QPIGS
                cmd = "QPIGS"
                payload = cmd.encode('ascii') + crc16_voltronic(cmd) + b'\r'
                ser.write(payload)
                time.sleep(0.3)
                res = ser.read(256)

                if res:
                    print(f"\n[RESP ON {p} @ {baud} baud] RAW ({len(res)}b): {res.hex()}", flush=True)
                    if b'(' in res:
                        ascii_str = res.decode('ascii', errors='ignore')
                        print(f"  --> Voltronic ASCII: {ascii_str}", flush=True)
                    elif res[0] in (1, 2, 3) and res[1] in (3, 4):
                        mb = parse_modbus_frame(res)
                        if mb:
                            print(f"  --> Modbus RTU Slave {mb[0]} Func {mb[1]} Regs: {mb[2]}", flush=True)

                ser.close()
            except Exception as e:
                pass

if __name__ == "__main__":
    main()
