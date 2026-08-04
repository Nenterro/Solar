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

def send_voltronic_cmd(dev, cmd: str) -> str:
    crc = crc16_voltronic(cmd)
    payload = cmd.encode('ascii') + crc + b'\x0d'
    dev.write(payload)

    response_bytes = bytearray()
    timeout = time.time() + 2.0
    while time.time() < timeout:
        chunk = dev.read(64, timeout_ms=500)
        if chunk:
            if isinstance(chunk, list):
                chunk = bytes(chunk)
            response_bytes.extend(chunk)
            if b'\r' in response_bytes:
                break
    if not response_bytes:
        return None
    return response_bytes.split(b'\r')[0].decode('ascii', errors='ignore')

def test_hidraw():
    import hid

    print("=" * 60)
    print("      DIRECT /dev/hidraw* DEVICE TESTER      ")
    print("=" * 60)

    hidraw_paths = sorted(glob.glob('/dev/hidraw*'))
    print(f"[+] Found hidraw nodes: {hidraw_paths}\n")

    for path in hidraw_paths:
        print(f"Testing node: {path}")
        try:
            dev = hid.device()
            dev.open_path(path.encode('utf-8'))
            print(f"  [+] Successfully opened {path}!")
            
            qid = send_voltronic_cmd(dev, "QID")
            qpigs = send_voltronic_cmd(dev, "QPIGS")
            qmod = send_voltronic_cmd(dev, "QMOD")
            
            print(f"  > QID Serial : {qid}")
            print(f"  > Mode QMOD  : {qmod}")
            print(f"  > QPIGS Raw  : {qpigs}")

            if qpigs and qpigs.startswith("("):
                parts = qpigs[1:].split()
                if len(parts) >= 16:
                    print("  --- Telemetry Breakdown ---")
                    print(f"      Grid Voltage : {parts[0]} V")
                    print(f"      Load Power   : {parts[5]} W")
                    print(f"      Battery Volt : {parts[8]} V")
                    print(f"      Battery %    : {parts[10]} %")
                    print(f"      Solar Power  : {parts[19] if len(parts) >= 20 else '0'} W")
            print()
            dev.close()
        except Exception as e:
            print(f"  [!] Could not open {path}: {e}\n")

if __name__ == "__main__":
    test_hidraw()
