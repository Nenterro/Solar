import serial, time
from serial_reader import crc16_voltronic

qid_cmd = b'QID'
qid_cmd = qid_cmd + crc16_voltronic(qid_cmd) + b'\r'

for port in ['/dev/ttyUSB0', '/dev/ttyUSB3']:
    print(f"--- {port} ---")
    try:
        s = serial.Serial(port, 2400, timeout=1.5)
        for i in range(5):
            s.reset_input_buffer()
            s.write(qid_cmd)
            resp = s.read_until(b'\r', size=50)
            if resp:
                print(f"Attempt {i}: {resp}")
            time.sleep(0.5)
        s.close()
    except Exception as e:
        print(f"Error: {e}")
