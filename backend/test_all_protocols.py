import os
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

def test_node_protocols(node_path: str):
    print(f"\n================ Testing {node_path} ================")

    # Protocol Variant A: Direct 8-byte chunk write
    cmd = "QPIGS"
    crc = crc16_voltronic(cmd)
    payload_a = cmd.encode('ascii') + crc + b'\x0d'

    # Protocol Variant B: Prepend Report ID 0x00
    payload_b = b'\x00' + payload_a

    # Protocol Variant C: Prepend Report ID 0x02
    payload_c = b'\x02' + payload_a

    variants = [("Standard ASCII", payload_a), ("Report ID 0x00", payload_b), ("Report ID 0x02", payload_c)]

    for label, payload in variants:
        try:
            fd = os.open(node_path, os.O_RDWR | os.O_NONBLOCK)

            for i in range(0, len(payload), 8):
                chunk = payload[i:i+8]
                if len(chunk) < 8:
                    chunk = chunk + b'\x00' * (8 - len(chunk))
                os.write(fd, chunk)

            time.sleep(0.2)
            response = bytearray()
            start = time.time()
            while time.time() - start < 1.0:
                try:
                    data = os.read(fd, 64)
                    if data:
                        response.extend(data)
                        if b'\r' in response:
                            break
                except BlockingIOError:
                    time.sleep(0.04)

            os.close(fd)

            if response:
                decoded = response.split(b'\r')[0].decode('ascii', errors='ignore')
                print(f"  [+] {label:15s} SUCCESS -> {repr(decoded)}")
            else:
                print(f"  [-] {label:15s} No Response")
        except Exception as e:
            print(f"  [!] {label:15s} Error: {e}")

def main():
    nodes = sorted(glob.glob('/dev/hidraw*'))
    print(f"Scanning protocols across nodes: {nodes}")
    for n in nodes:
        test_node_protocols(n)

if __name__ == "__main__":
    main()
