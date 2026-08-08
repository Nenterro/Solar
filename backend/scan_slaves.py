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

def test_slave(ser, slave_id):
    req_body = bytes([slave_id, 0x03, 0x00, 0x00, 0x00, 0x0A])
    req = req_body + crc16_modbus(req_body)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(req)
    time.sleep(0.1)
    resp = ser.read(1024)
    if resp:
        print(f"  Slave {slave_id} responded! {resp.hex()}")
        return True
    return False

def scan_port(port):
    print(f"\n--- SCANNING {port} ---")
    try:
        ser = serial.Serial(port, 9600, timeout=0.2)
        for slave_id in range(1, 10):
            test_slave(ser, slave_id)
        ser.close()
    except Exception as e:
        print(f"Error on {port}: {e}")

if __name__ == "__main__":
    scan_port("/dev/ttyUSB1")
    scan_port("/dev/ttyUSB2")
    scan_port("/dev/ttyUSB3")
