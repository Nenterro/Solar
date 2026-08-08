import serial
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

def test_cmd(ser, cmd_str):
    crc = crc16_voltronic(cmd_str)
    full_cmd = cmd_str.encode('ascii') + crc + b'\r'
    ser.reset_input_buffer()
    ser.write(full_cmd)
    time.sleep(0.5)
    resp = ser.read(1024)
    if resp:
        print(f"  {cmd_str} -> {resp.hex()} | {resp.decode('ascii', errors='ignore')}")
    else:
        print(f"  {cmd_str} -> NO RESPONSE")

def main():
    cmds = ["QPIGS", "QPIGS0"]
    for baud in [2400, 9600, 19200]:
        print(f"\n--- /dev/ttyUSB1 at {baud} baud ---")
        try:
            ser = serial.Serial("/dev/ttyUSB1", baud, timeout=1.0)
            for cmd in cmds:
                test_cmd(ser, cmd)
            ser.close()
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
