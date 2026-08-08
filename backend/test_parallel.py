import serial
import time

crc_table = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
    0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef
]
# We'll just use the standard voltronic crc for now
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

def test_cmd(ser, cmd):
    crc = crc16_voltronic(cmd)
    ser.reset_input_buffer()
    ser.write(cmd.encode('ascii') + crc + b'\r')
    time.sleep(0.3)
    resp = ser.read(1024)
    if resp:
        print(f"  {cmd} -> {resp.hex()} | {resp.decode('ascii', errors='ignore')}")
    else:
        print(f"  {cmd} -> NO RESPONSE")

def main():
    cmds = ["QPIGS", "QPIGS0", "QPIGS1", "QPIGS2", "QPIRI", "QPI", "QMD"]
    for port in ["/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyUSB3"]:
        print(f"\n--- {port} at 2400 baud ---")
        try:
            ser = serial.Serial(port, 2400, timeout=0.5)
            for cmd in cmds:
                test_cmd(ser, cmd)
            ser.close()
        except Exception as e:
            print(f"Error on {port}: {e}")

if __name__ == "__main__":
    main()
