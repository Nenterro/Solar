import serial
import glob
import time
import sys

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

def main():
    ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2", "/dev/ttyUSB3"]
    print(f"=== PROBING ALL 4 CONNECTED SERIAL PORTS: {ports} ===", flush=True)

    qpigs_cmd = "QPIGS".encode('ascii') + crc16_voltronic("QPIGS") + b'\r'

    for p in ports:
        print(f"\n==========================================", flush=True)
        print(f"TESTING PORT: {p}", flush=True)
        print(f"==========================================", flush=True)
        
        for baud in [2400, 9600, 19200]:
            for rts in [True, False]:
                for dtr in [True, False]:
                    try:
                        ser = serial.Serial(p, baud, timeout=0.4)
                        ser.rts = rts
                        ser.dtr = dtr
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()

                        # 1. Test QPIGS
                        ser.write(qpigs_cmd)
                        time.sleep(0.15)
                        res = ser.read(256)
                        if res and res != b'\x00' * len(res):
                            print(f"  [SUCCESS {p} @ {baud} baud RTS={rts} DTR={dtr}] QPIGS ({len(res)}b): {res.hex()}", flush=True)
                            if b'(' in res:
                                print(f"    ASCII: {res.decode('ascii', errors='ignore')}", flush=True)

                        # 2. Test Modbus Slave 1, 2, 3 (Reg 0, qty 5)
                        for slave_id in [1, 2, 3]:
                            mb_req = bytes([slave_id, 0x03, 0x00, 0x00, 0x00, 0x05])
                            mb_payload = mb_req + crc16_modbus(mb_req)
                            ser.reset_input_buffer()
                            ser.reset_output_buffer()
                            ser.write(mb_payload)
                            time.sleep(0.15)
                            res_mb = ser.read(256)
                            if res_mb and res_mb != b'\x00' * len(res_mb):
                                print(f"  [SUCCESS {p} @ {baud} baud Slave {slave_id}] Modbus ({len(res_mb)}b): {res_mb.hex()}", flush=True)

                        ser.close()
                    except Exception as e:
                        pass

if __name__ == "__main__":
    main()
