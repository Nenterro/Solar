import sys
import os
import time
import serial
import glob

def crc16(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = (crc << 1)
            crc &= 0xFFFF
    
    high = (crc >> 8) & 0xFF
    low = crc & 0xFF
    
    if high in (0x0D, 0x0A, 0x28):
        high += 1
    if low in (0x0D, 0x0A, 0x28):
        low += 1
        
    return bytes([high, low])

def make_cmd(cmd_str: str) -> bytes:
    cmd_bytes = cmd_str.encode('ascii')
    crc = crc16(cmd_bytes)
    return cmd_bytes + crc + b'\r'

TEST_COMMANDS = ["QPI", "QID", "QPIGS", "QPGS0", "QPGS1", "QPGS2", "QMOD", "QPIWS", "QFLAG"]
BAUD_RATES = [2400, 9600, 19200]

def probe_port(port_path):
    print(f"\n==================================================")
    print(f"PROBING SERIAL PORT: {port_path}")
    print(f"==================================================")

    for baud in BAUD_RATES:
        print(f"\n--- Testing Baud Rate: {baud} baud ---")
        try:
            ser = serial.Serial(
                port=port_path,
                baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.5
            )
            
            # Flush existing buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            for cmd in TEST_COMMANDS:
                raw_payload = make_cmd(cmd)
                ser.write(raw_payload)
                time.sleep(0.3)
                
                resp = ser.read(256)
                if resp:
                    print(f"  [SUCCESS @ {baud} baud] CMD: {cmd:6s} -> RAW RESPONSE ({len(resp)} bytes): {resp}")
                    try:
                        print(f"    ASCII STRING: {resp.decode('ascii', errors='ignore')}")
                    except Exception:
                        pass
                else:
                    # Also try plain command without CRC just in case (some inverters accept plain ASCII + \r)
                    ser.write(cmd.encode('ascii') + b'\r')
                    time.sleep(0.3)
                    resp_no_crc = ser.read(256)
                    if resp_no_crc:
                        print(f"  [SUCCESS NO-CRC @ {baud} baud] CMD: {cmd:6s} -> RAW RESPONSE ({len(resp_no_crc)} bytes): {resp_no_crc}")

            ser.close()
        except Exception as e:
            print(f"  Error accessing port {port_path} at {baud} baud: {e}")

def main():
    ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    if not ports:
        print("No /dev/ttyUSB* or /dev/ttyACM* devices found on system!")
        return

    print(f"Found {len(ports)} serial devices: {ports}")
    for p in ports:
        probe_port(p)

if __name__ == "__main__":
    main()
