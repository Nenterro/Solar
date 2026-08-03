import os
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

def query_node(node_path: str, cmd: str) -> str:
    try:
        fd = os.open(node_path, os.O_RDWR | os.O_NONBLOCK)
        crc = crc16_voltronic(cmd)
        payload = cmd.encode('ascii') + crc + b'\x0d'

        for i in range(0, len(payload), 8):
            chunk = payload[i:i+8]
            if len(chunk) < 8:
                chunk = chunk + b'\x00' * (8 - len(chunk))
            os.write(fd, chunk)

        time.sleep(0.12)
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
            return response_bytes.split(b'\r')[0].decode('ascii', errors='ignore')
        return None
    except Exception as e:
        return None

INVERTERS_MAP = [
    {"node": "/dev/hidraw0", "id": "inv1", "name": "Inverter 1"},
    {"node": "/dev/hidraw1", "id": "inv2", "name": "Inverter 2"},
    {"node": "/dev/hidraw2", "id": "inv3", "name": "Inverter 3"},
]

def main():
    print("=" * 70)
    print("      LIVE 3-INVERTER REAL-TIME USB HID TELEMETRY REPORT      ")
    print("=" * 70)

    total_solar = 0.0
    total_load = 0.0
    total_bat_w = 0.0

    for inv in INVERTERS_MAP:
        node = inv["node"]
        name = inv["name"]
        print(f"\n--- {name.upper()} ({node}) ---")
        
        sn = query_node(node, "QID")
        mod = query_node(node, "QMOD")
        qpigs = query_node(node, "QPIGS")

        print(f"  Serial Number (QID) : {sn[1:].strip() if sn else 'N/A'}")
        print(f"  Operating Mode      : {mod[1:].strip() if mod else 'N/A'}")

        if qpigs and qpigs.startswith("("):
            parts = qpigs[1:].split()
            if len(parts) >= 16:
                grid_v = float(parts[0])
                ac_load_w = float(parts[5])
                load_pct = float(parts[6])
                bat_v = float(parts[8])
                bat_chg_a = float(parts[9])
                bat_soc = float(parts[10])
                temp = float(parts[11])
                pv_v = float(parts[13])
                bat_dischg_a = float(parts[15]) if len(parts) >= 16 else 0.0
                pv_w = float(parts[19]) if len(parts) >= 20 else (float(parts[12]) * pv_v)

                bat_w = (bat_chg_a - bat_dischg_a) * bat_v

                total_solar += pv_w
                total_load += ac_load_w
                total_bat_w += bat_w

                print(f"  Grid Line Voltage   : {grid_v:.1f} V @ {parts[1]} Hz")
                print(f"  Home Load Power     : {ac_load_w:.0f} W ({load_pct}% load)")
                print(f"  Solar PV Input      : {pv_w:.0f} W ({pv_v:.1f} V)")
                print(f"  Battery Status      : {bat_v:.2f} V ({bat_soc:.0f}%) | Net: {bat_w:+.0f} W")
                print(f"  Inverter Temp       : {temp:.0f} deg C")
        else:
            print("  [!] Failed to read QPIGS telemetry")

    print("\n" + "=" * 70)
    print("      COMBINED SYSTEM TOTALS (ALL INVERTERS)      ")
    print("=" * 70)
    print(f"  Total Solar Generation : {total_solar / 1000.0:.2f} kW ({total_solar:.0f} W)")
    print(f"  Total Home Load Power  : {total_load / 1000.0:.2f} kW ({total_load:.0f} W)")
    print(f"  Total Battery Net Power: {total_bat_w / 1000.0:.2f} kW ({total_bat_w:+.0f} W)")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
