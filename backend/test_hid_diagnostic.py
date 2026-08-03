import sys
import time
import logging
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("HID_DIAGNOSTIC")

def crc16_voltronic(command: str) -> bytes:
    """
    Calculate Voltronic CRC16 (XMODEM variant) for a given command string.
    """
    crc = 0x0000
    for char in command:
        crc = crc ^ (ord(char) << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return bytes([crc >> 8, crc & 0xFF])

def send_voltronic_cmd(dev, cmd: str) -> Optional[str]:
    """
    Send raw Voltronic command over USB HID and read ASCII response.
    """
    crc = crc16_voltronic(cmd)
    payload = cmd.encode('ascii') + crc + b'\x0d'

    try:
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
    except Exception as e:
        logger.error(f"Error executing command '{cmd}': {e}")
        return None

def test_hid_devices():
    print("=" * 60)
    print("      SOLAR INVERTER USB HID RAW DIAGNOSTIC TOOL      ")
    print("=" * 60)

    try:
        import hid
    except ImportError:
        print("ERROR: 'hidapi' package not installed. Run: pip install hidapi")
        sys.exit(1)

    # VendorID 0x0665 (1637), ProductID 0x5161 (20833) - Voltronic / Knox HID
    devices = hid.enumerate(0x0665, 0x5161)
    if not devices:
        print("\n[!] No 0665:5161 HID devices found. Checking all HID devices...")
        all_devs = hid.enumerate()
        print(f"Found {len(all_devs)} total HID devices on host:")
        for d in all_devs:
            print(f"  - Path: {d.get('path')} | VID: {hex(d.get('vendor_id',0))} | PID: {hex(d.get('product_id',0))} | Product: {d.get('product_string')}")
        return

    print(f"\n[+] Found {len(devices)} Knox/Voltronic USB HID Inverter Device(s)!\n")

    COMMANDS_TO_TEST = [
        ("QID", "Inverter Serial Number"),
        ("QPIGS", "General Status Telemetry (Grid/PV/Battery/Load)"),
        ("QMOD", "Device Operating Mode"),
        ("QPIWS", "Warning Status Flags"),
        ("QPIRI", "Rating Information")
    ]

    for idx, d_info in enumerate(devices, 1):
        path = d_info.get('path')
        print(f"--- [INVERTER DEVICE #{idx}] ---")
        print(f"Device Path : {path}")
        print(f"Vendor ID   : {hex(d_info.get('vendor_id', 0))}")
        print(f"Product ID  : {hex(d_info.get('product_id', 0))}")
        print(f"Manufacturer: {d_info.get('manufacturer_string', 'N/A')}")
        print(f"Product     : {d_info.get('product_string', 'N/A')}\n")

        try:
            dev = hid.device()
            dev.open_path(path)
            print("  [+] Connection opened successfully! Querying read-only commands...\n")

            for cmd, desc in COMMANDS_TO_TEST:
                raw_resp = send_voltronic_cmd(dev, cmd)
                print(f"  > Command: {cmd} ({desc})")
                print(f"    Raw Response: {repr(raw_resp)}")

                if cmd == "QPIGS" and raw_resp and raw_resp.startswith("("):
                    tokens = raw_resp[1:].split()
                    print(f"    Parsed Tokens Count: {len(tokens)}")
                    if len(tokens) >= 16:
                        print("    --- Parsed QPIGS Telemetry Fields ---")
                        print(f"    1. Grid Voltage         : {tokens[0]} V")
                        print(f"    2. Grid Frequency       : {tokens[1]} Hz")
                        print(f"    3. AC Output Voltage    : {tokens[2]} V")
                        print(f"    4. AC Output Frequency  : {tokens[3]} Hz")
                        print(f"    5. AC Apparent Power    : {tokens[4]} VA")
                        print(f"    6. AC Active Power      : {tokens[5]} W  <-- (Home Load)")
                        print(f"    7. Load Percentage      : {tokens[6]} %")
                        print(f"    8. Bus Voltage          : {tokens[7]} V")
                        print(f"    9. Battery Voltage      : {tokens[8]} V")
                        print(f"   10. Battery Charge Curr  : {tokens[9]} A")
                        print(f"   11. Battery Capacity     : {tokens[10]} %")
                        print(f"   12. Inverter Temperature : {tokens[11]} deg C")
                        print(f"   13. PV Input Current     : {tokens[12]} A")
                        print(f"   14. PV Input Voltage     : {tokens[13]} V")
                        print(f"   15. Battery Dischg Curr  : {tokens[15] if len(tokens) > 15 else 'N/A'} A")
                        if len(tokens) >= 20:
                            print(f"   20. PV Input Power       : {tokens[19]} W  <-- (Solar Yield)")
                print()

            dev.close()
        except Exception as e:
            print(f"  [!] Failed to read from device {path}: {e}\n")

if __name__ == "__main__":
    test_hid_devices()
