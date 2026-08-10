import serial, time

def crc16(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return bytes([(crc >> 8) & 0xFF, crc & 0xFF])

def test_cmd(port, cmd):
    try:
        ser = serial.Serial(port, 2400, timeout=1.0)
        cb = cmd.encode('ascii')
        ser.write(cb + crc16(cb) + b'\r')
        res = ser.read(128).decode('ascii', errors='ignore')
        ser.close()
        return res
    except Exception as e:
        return str(e)

op2_queries = [
    "QOP2", "QPO2", "QPOP2", "QOP2V", "QPO2V", "QOP2OFF", "QOP2ON", "QPO2OFF", "QPO2ON", "Q2OP", "Q2P", "QOP2S"
]

op2_set_candidates = [
    "POP252.0", "POP250.0", "POP254.0", "POP256.5",
    "PO252.0", "PO250.0", "PO254.0", "PO256.5",
    "PO2V52.0", "PO2V50.0", "PO2V54.0", "PO2V56.5",
    "PO2OFF52.0", "PO2OFF50.0", "PO2OFF54.0", "PO2OFF56.5",
    "PO2ON54.0", "PO2ON57.0",
    "PBT252.0", "PBT250.0", "PBT254.0", "PBT256.5",
    "PBDV252.0", "PSDV252.0", "PBCV252.0"
]

ports = {
    "inv1": "/dev/ttyUSB1",
    "inv2": "/dev/ttyUSB2",
    "inv3": "/dev/ttyUSB3"
}

print("=========================================================================")
print("TESTING OP2 QUERIES AND SET COMMANDS OVER RS232")
print("=========================================================================")

for name, port in ports.items():
    print(f"\n--- {name.upper()} ({port}) QUERIES ---", flush=True)
    for q in op2_queries:
        res = test_cmd(port, q)
        if res and not res.startswith("(NAK"):
            print(f"  !!! VALID QUERY RESPONSE: {q:10s} -> {repr(res)}", flush=True)
        else:
            pass
        time.sleep(0.05)

    print(f"\n--- {name.upper()} ({port}) SET COMMANDS ---", flush=True)
    for s in op2_set_candidates:
        res = test_cmd(port, s)
        if res and not res.startswith("(NAK"):
            print(f"  !!! VALID SET RESPONSE: {s:15s} -> {repr(res)}", flush=True)
        else:
            pass
        time.sleep(0.05)
