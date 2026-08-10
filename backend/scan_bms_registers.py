import serial, struct, time

port = "/dev/ttyUSB0"
baudrate = 9600

def crc16_modbus(data: bytearray) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc

print("=========================================================================")
print(f"SCANNING KNOX BMS MODBUS REGISTERS ON {port} AT {baudrate} BAUD")
print("=========================================================================")

try:
    s = serial.Serial(port, baudrate, timeout=1.0)
    
    # Test reading multiple register blocks starting at 0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
    for start_reg in [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
        req = bytearray(struct.pack('>BBHH', 1, 3, start_reg, 10))
        crc = crc16_modbus(req)
        full_cmd = req + struct.pack('<H', crc)
        
        s.reset_input_buffer()
        s.write(full_cmd)
        time.sleep(0.2)
        res = s.read(1024)
        
        if len(res) >= 5 and res[0] == 0x01 and res[1] == 0x03:
            print(f"\n--- REGISTER BLOCK Starting at Reg {start_reg} (RAW LEN={len(res)}) ---")
            raw_hex = " ".join(f"{b:02X}" for b in res)
            print(f"  HEX: {raw_hex}")
            
            # Print parsed 16-bit registers
            payload = res[3:-2] if len(res) >= 7 else res[3:]
            regs = []
            for i in range(0, len(payload) - 1, 2):
                val_u = struct.unpack('>H', payload[i:i+2])[0]
                val_s = struct.unpack('>h', payload[i:i+2])[0]
                reg_num = start_reg + (i // 2)
                regs.append(f"R{reg_num}:{val_u}({val_s})")
            print("  PARSED REGS: " + ", ".join(regs))
        else:
            print(f"Reg {start_reg}: No response / NAK ({len(res)} bytes)")
        time.sleep(0.1)

    s.close()
except Exception as e:
    print(f"Error accessing {port}: {e}")
