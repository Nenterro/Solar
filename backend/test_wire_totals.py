import serial
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

def send_cmd(ser, cmd_str):
    crc = crc16(cmd_str)
    payload = cmd_str.encode('ascii') + crc + b'\r'
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(payload)
    time.sleep(0.3)
    return ser.read(256)

def main():
    port = "/dev/ttyUSB0"
    print(f"=== TESTING DAILY TOTAL COMMANDS OVER WIRE ON {port} ===", flush=True)

    for baud in [2400, 9600]:
        try:
            ser = serial.Serial(port, baud, timeout=1.5)
            print(f"\n--- Baud: {baud} ---", flush=True)

            # Test QET (Query Energy Today)
            today_qet = f"QET20260804"
            resp = send_cmd(ser, today_qet)
            if resp:
                print(f"  [QET RESP] {resp}", flush=True)
                print(f"    ASCII: {resp.decode('ascii', errors='ignore')}", flush=True)

            # Test Parallel Status QPGS0, QPGS1, QPGS2
            for i in range(3):
                qpgs_cmd = f"QPGS{i}"
                resp_p = send_cmd(ser, qpgs_cmd)
                if resp_p:
                    print(f"  [QPGS{i} RESP] {resp_p}", flush=True)
                    print(f"    ASCII: {resp_p.decode('ascii', errors='ignore')}", flush=True)

            ser.close()
        except Exception as e:
            print(f"  Error on {port} @ {baud}: {e}", flush=True)

if __name__ == "__main__":
    main()
