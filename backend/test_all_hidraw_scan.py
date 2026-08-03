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

def test_node(node_path: str):
    try:
        fd = os.open(node_path, os.O_RDWR | os.O_NONBLOCK)
        cmd = "QID"
        crc = crc16_voltronic(cmd)
        payload = cmd.encode('ascii') + crc + b'\x0d'

        for i in range(0, len(payload), 8):
            chunk = payload[i:i+8]
            if len(chunk) < 8:
                chunk = chunk + b'\x00' * (8 - len(chunk))
            os.write(fd, chunk)

        time.sleep(0.15)
        response_bytes = bytearray()
        start = time.time()
        while time.time() - start < 0.8:
            try:
                data = os.read(fd, 64)
                if data:
                    response_bytes.extend(data)
                    if b'\r' in response_bytes:
                        break
            except BlockingIOError:
                time.sleep(0.04)

        os.close(fd)
        if response_bytes:
            raw_str = response_bytes.split(b'\r')[0].decode('ascii', errors='ignore')
            return raw_str
        return None
    except Exception as e:
        return f"ERROR: {e}"

def main():
    print("=" * 60)
    print("      DEEP DISCOVERY SCANNER FOR INVERTER HID NODES      ")
    print("=" * 60)

    all_hidraw = sorted(glob.glob('/dev/hidraw*'))
    all_tty = sorted(glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))

    print(f"[+] All hidraw nodes in container: {all_hidraw}")
    print(f"[+] All serial tty nodes in container: {all_tty}\n")

    for node in all_hidraw:
        res = test_node(node)
        print(f"Node {node:15s} -> QID Result: {res}")

if __name__ == "__main__":
    main()
