import serial
import time
import struct
import glob
import logging

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

def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return bytes([crc & 0xFF, crc >> 8])

def decode_all(raw_bytes: bytes, label: str):
    if not raw_bytes:
        print(f"{label}: NO RESPONSE")
        return
        
    print(f"{label}:")
    print(f"  RAW: {raw_bytes.hex()}")
    
    # Try ASCII
    try:
        asc = raw_bytes.decode('ascii', errors='ignore').strip()
        if asc:
            print(f"  ASCII: {asc}")
    except:
        pass
        
    # Try Float32 (IEEE-754)
    found_float = False
    for i in range(len(raw_bytes) - 3):
        if raw_bytes[i] in (0x41, 0x42, 0x43, 0x44):
            try:
                fv = struct.unpack('>f', raw_bytes[i:i+4])[0]
                if 10.0 <= fv <= 25000.0:
                    print(f"  Float32 @ offset {i}: {fv:.2f} W ({fv/1000.0:.2f} kW)")
                    found_float = True
            except:
                pass
                
    # Try Int16 (Big-Endian)
    found_int = False
    for i in range(len(raw_bytes) - 1):
        v = (raw_bytes[i] << 8) | raw_bytes[i+1]
        if 100 <= v <= 25000:
            print(f"  Int16 @ offset {i:02d}: {v} W ({v/1000.0:.2f} kW)")
            found_int = True
            
def test_port(port):
    print(f"\n======================================")
    print(f"TESTING PORT: {port}")
    print(f"======================================")
    
    for baud in [2400, 9600, 19200]:
        print(f"\n--- BAUD RATE: {baud} ---")
        try:
            ser = serial.Serial(port, baud, timeout=0.3)
            
            # 1. Plain QPIGS
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(b"QPIGS\r")
            time.sleep(0.15)
            r = ser.read(256)
            decode_all(r, "Plain QPIGS\\r")
            
            # 2. QPIGS + CRC
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            cmd = "QPIGS"
            ser.write(cmd.encode('ascii') + crc16_voltronic(cmd) + b'\r')
            time.sleep(0.15)
            r = ser.read(256)
            decode_all(r, "QPIGS + CRC + \\r")
            
            # 3. Modbus Function 3 (Regs 0-10) Slave 1
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            req = bytes([1, 0x03, 0x00, 0x00, 0x00, 0x0A])
            ser.write(req + crc16_modbus(req))
            time.sleep(0.15)
            r = ser.read(256)
            decode_all(r, "Modbus Slave 1 Reg 0-10")
            
            ser.close()
        except Exception as e:
            print(f"Error on {port} @ {baud}: {e}")

def main():
    ports = sorted(glob.glob("/dev/ttyUSB*"))
    for p in ports:
        test_port(p)

if __name__ == "__main__":
    main()
