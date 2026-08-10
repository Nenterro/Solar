import serial, time, struct

def modbus_crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for i in range(8):
            if (crc & 0x0001) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)

def read_holding_regs(port: str, slave_addr: int, start_reg: int, count: int) -> list:
    try:
        ser = serial.Serial(port, 2400, timeout=0.8)
        # Read Holding Registers function 0x03
        msg = struct.pack('>BBHH', slave_addr, 0x03, start_reg, count)
        msg += modbus_crc16(msg)
        ser.write(msg)
        resp = ser.read(5 + count * 2)
        ser.close()
        if len(resp) >= 5 + count * 2:
            vals = []
            for i in range(count):
                val = struct.unpack('>H', resp[3+i*2:5+i*2])[0]
                vals.append(val)
            return vals
        return []
    except Exception:
        return []

ports = {
    "inv1": "/dev/ttyUSB1", # expecting 52 or 520
    "inv2": "/dev/ttyUSB2", # expecting 50 or 500
    "inv3": "/dev/ttyUSB3"  # expecting 54 or 540
}

print("=== TESTING MODBUS RTU OVER RS232 FOR AC2 REGISTERS ===")
for addr in [1, 2]:
    for start in range(0, 300, 10):
        res1 = read_holding_regs(ports["inv1"], addr, start, 10)
        res2 = read_holding_regs(ports["inv2"], addr, start, 10)
        res3 = read_holding_regs(ports["inv3"], addr, start, 10)
        if res1 or res2 or res3:
            print(f"Slave {addr} Reg {start:3d}-{start+9:3d}:")
            print(f"  Inv1: {res1}")
            print(f"  Inv2: {res2}")
            print(f"  Inv3: {res3}")
