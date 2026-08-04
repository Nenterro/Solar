import serial
import time

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

def main():
    ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyUSB3"]
    print("=== TESTING MODBUS SLAVES 1, 2, 3 ACROSS ALL 4 PORTS ===", flush=True)

    for p in ports:
        for baud in [9600, 2400]:
            try:
                ser = serial.Serial(p, baud, timeout=0.25)
                for slave in [1, 2, 3]:
                    mb_req = bytes([slave, 0x03, 0x00, 0x00, 0x00, 0x05])
                    mb_payload = mb_req + crc16_modbus(mb_req)
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    ser.write(mb_payload)
                    time.sleep(0.12)
                    res = ser.read(128)
                    if res and len(res) >= 5 and res[0] == slave:
                        print(f"[FOUND PORT {p} @ {baud} baud SLAVE {slave}] ({len(res)}b): {res.hex()}", flush=True)
                ser.close()
            except Exception as e:
                pass

if __name__ == "__main__":
    main()
