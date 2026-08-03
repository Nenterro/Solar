import os
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

def test_raw_hidraw():
    print("=" * 60)
    print("   RAW LINUX /dev/hidraw* FILE READ/WRITE TESTER   ")
    print("=" * 60)

    nodes = sorted(glob.glob('/dev/hidraw*'))
    print(f"[+] Found hidraw nodes: {nodes}\n")

    COMMANDS = ["QID", "QPIGS", "QMOD"]

    for node in nodes:
        print(f"--- Testing {node} via Direct File I/O ---")
        try:
            # Open raw hidraw device with non-blocking os.open or binary rw
            fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
            print(f"  [+] Successfully opened file descriptor for {node}!")

            for cmd in COMMANDS:
                crc = crc16_voltronic(cmd)
                payload = cmd.encode('ascii') + crc + b'\x0d'

                # Write 8-byte chunks
                for i in range(0, len(payload), 8):
                    chunk = payload[i:i+8]
                    if len(chunk) < 8:
                        chunk = chunk + b'\x00' * (8 - len(chunk))
                    os.write(fd, chunk)

                time.sleep(0.15)

                response_bytes = bytearray()
                start = time.time()
                while time.time() - start < 1.0:
                    try:
                        data = os.read(fd, 64)
                        if data:
                            response_bytes.extend(data)
                            if b'\r' in response_bytes:
                                break
                    except BlockingIOError:
                        time.sleep(0.05)

                if response_bytes:
                    raw_str = response_bytes.split(b'\r')[0].decode('ascii', errors='ignore')
                    print(f"  > Command {cmd}: {raw_str}")
                    if cmd == "QPIGS" and raw_str.startswith("("):
                        parts = raw_str[1:].split()
                        print(f"    - Grid V: {parts[0]}V | Load: {parts[5]}W | Bat V: {parts[8]}V | Bat %: {parts[10]}%")
                else:
                    print(f"  > Command {cmd}: (No Response)")

            os.close(fd)
            print()
        except Exception as e:
            print(f"  [!] Direct OS Open Error on {node}: {e}\n")

if __name__ == "__main__":
    test_raw_hidraw()
