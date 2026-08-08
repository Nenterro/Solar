import serial
import time

def crc16(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    
    # specific Voltronic crc adjustments
    crc_high = (crc >> 8) & 0xFF
    crc_low = crc & 0xFF
    
    if crc_high in [0x0A, 0x0D, 0x28]:
        crc_high += 1
    if crc_low in [0x0A, 0x0D, 0x28]:
        crc_low += 1
        
    return bytes([crc_high, crc_low])

def clean_response(raw_bytes: bytes) -> str:
    # Filter out 0xFF noise
    cleaned = bytes([b for b in raw_bytes if b != 0xFF and b != 0x00])
    try:
        return cleaned.decode('ascii', errors='ignore')
    except:
        return cleaned.hex()

def test_command(ser, cmd_str: str):
    cmd_bytes = cmd_str.encode('ascii')
    crc_bytes = crc16(cmd_bytes)
    full_cmd = cmd_bytes + crc_bytes + b'\r'
    
    print(f"Testing {cmd_str}...")
    ser.reset_input_buffer()
    ser.write(full_cmd)
    
    # Read response
    time.sleep(0.5)
    response = b""
    while ser.in_waiting:
        response += ser.read(ser.in_waiting)
        time.sleep(0.1)
        
    if not response:
        print(f"  {cmd_str} -> NO RESPONSE")
    else:
        text = clean_response(response)
        print(f"  {cmd_str} -> {text.strip()}")

def main():
    cmds = [
        "QPI",      # Protocol ID
        "QID",      # Serial Number
        "QVFW",     # Main CPU Firmware
        "QVFW2",    # Secondary CPU Firmware
        "QPIGS",    # General Status
        "QPIGS0",   # Sometimes used for Phase 1
        "QMOD",     # Device Mode (Line, Battery, Fault, etc)
        "QFLAG",    # Device Flags
        "QPIWS",    # Warning Status
        "QDI",      # Default Settings
        "VFW",      # Sometimes firmware is just VFW
        "PI",       # Sometimes protocol is just PI
    ]
    
    try:
        # We know 2400 is the correct baud rate from the NAK test!
        ser = serial.Serial('/dev/ttyUSB1', 2400, timeout=1)
        print("Connected to /dev/ttyUSB1 at 2400 baud. Testing commands...")
        
        for cmd in cmds:
            test_command(ser, cmd)
            
        ser.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
