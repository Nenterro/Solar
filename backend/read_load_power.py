import serial
import time

def main():
    try:
        ser = serial.Serial("/dev/ttyUSB0", 2400, timeout=1.0)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Voltronic QPIGS command with CRC16
        cmd = b"QPIGS\xb7\xa9\r"
        ser.write(cmd)
        time.sleep(0.3)
        resp = ser.read(256)
        
        if len(resp) >= 12:
            print("RAW HEX:", resp.hex())
            # Parse registers:
            # Reg 0 (bytes 4..5): Grid Voltage
            # Reg 1 (bytes 6..7): Grid Frequency
            # Reg 2 (bytes 8..9): Load Power High Word
            # Reg 3 (bytes 10..11): Load Power Low Word
            reg2 = (resp[8] << 8) | resp[9]
            reg3 = (resp[10] << 8) | resp[11]
            load_watts = (reg2 << 16) | reg3
            print(f"REG 2: {reg2} (0x{reg2:04X})")
            print(f"REG 3: {reg3} (0x{reg3:04X})")
            print(f"CALCULATED LOAD POWER: {load_watts} Watts ({load_watts / 1000.0:.2f} kW)")
        else:
            print("RESPONSE TOO SHORT:", resp)
        ser.close()
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    main()
