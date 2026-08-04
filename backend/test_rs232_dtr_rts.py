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

def test_combo(port, baud, dtr, rts, cmd_str):
    label = f"{port} @ {baud}b (DTR={dtr}, RTS={rts})"
    try:
        ser = serial.Serial(port, baud, timeout=1.2)
        ser.dtr = dtr
        ser.rts = rts
        time.sleep(0.1)

        ser.reset_input_buffer()
        ser.reset_output_buffer()

        crc = crc16(cmd_str)
        payload = cmd_str.encode('ascii') + crc + b'\r'
        ser.write(payload)
        time.sleep(0.4)

        res = ser.read(256)
        ser.close()

        if res:
            print(f"[FOUND RESPONSE] {label} CMD: {cmd_str} -> RAW ({len(res)}b): {res}", flush=True)
            try:
                print(f"  ASCII: {res.decode('ascii', errors='ignore')}", flush=True)
            except Exception:
                pass
            return True
        return False
    except Exception as e:
        return False

def main():
    print("=== TESTING RS232 WITH DTR/RTS CONTROL ===", flush=True)
    cmds = ["QPIGS", "QPI", "QID", "QPGS0"]
    ports = ["/dev/ttyUSB0", "/dev/ttyUSB1"]
    
    for port in ports:
        for baud in [2400, 9600, 19200]:
            for dtr in [True, False]:
                for rts in [True, False]:
                    for cmd in cmds:
                        if test_combo(port, baud, dtr, rts, cmd):
                            print(f"*** MATCH SUCCESSFUL ON {port} @ {baud} baud! ***", flush=True)

if __name__ == "__main__":
    main()
