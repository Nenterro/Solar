import sys
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

def main():
    print("=" * 60)
    print("      USB BUS DIRECT ENUMERATION TESTER (0665:5161)      ")
    print("=" * 60)

    try:
        import hid
    except ImportError:
        print("Please install hidapi: pip install hidapi")
        sys.exit(1)

    devices = hid.enumerate(0x0665, 0x5161)
    print(f"\n[+] Found {len(devices)} Cypress 0665:5161 devices via HIDAPI:")

    for idx, d in enumerate(devices, 1):
        print(f"\n--- Inverter #{idx} ---")
        print(f"  Path      : {d.get('path')}")
        print(f"  VendorID  : {hex(d.get('vendor_id',0))}")
        print(f"  ProductID : {hex(d.get('product_id',0))}")
        print(f"  Serial    : {d.get('serial_number')}")

        try:
            dev = hid.device()
            dev.open_path(d.get('path'))
            dev.set_nonblocking(1)

            # Query QID
            cmd = "QID"
            crc = crc16_voltronic(cmd)
            payload = cmd.encode('ascii') + crc + b'\x0d'

            dev.write(payload)
            time.sleep(0.2)

            response = bytearray()
            start = time.time()
            while time.time() - start < 1.0:
                chunk = dev.read(64, timeout_ms=300)
                if chunk:
                    if isinstance(chunk, list):
                        chunk = bytes(chunk)
                    response.extend(chunk)
                    if b'\r' in response:
                        break

            print(f"  > QID Response: {repr(response.decode('ascii', errors='ignore'))}")

            # Query QPIGS
            cmd = "QPIGS"
            crc = crc16_voltronic(cmd)
            payload = cmd.encode('ascii') + crc + b'\x0d'

            dev.write(payload)
            time.sleep(0.2)

            response = bytearray()
            start = time.time()
            while time.time() - start < 1.0:
                chunk = dev.read(64, timeout_ms=300)
                if chunk:
                    if isinstance(chunk, list):
                        chunk = bytes(chunk)
                    response.extend(chunk)
                    if b'\r' in response:
                        break

            raw_qpigs = response.decode('ascii', errors='ignore').strip()
            print(f"  > QPIGS Raw   : {repr(raw_qpigs)}")

            if raw_qpigs.startswith("("):
                parts = raw_qpigs[1:].split()
                if len(parts) >= 16:
                    print(f"    - Grid: {parts[0]}V | Load: {parts[5]}W | Bat Volt: {parts[8]}V | Bat %: {parts[10]}%")

            dev.close()
        except Exception as e:
            print(f"  [!] Device open error on {d.get('path')}: {e}")

if __name__ == "__main__":
    main()
