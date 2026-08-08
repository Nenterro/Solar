import serial, time
from serial_reader import crc16_voltronic

for port in ['/dev/ttyUSB1', '/dev/ttyUSB2']:
    print(f"\n=================== {port} ===================")
    try:
        s = serial.Serial(port, 2400, timeout=1.5)
        # QID
        cmd_qid = b'QID' + crc16_voltronic(b'QID') + b'\r'
        s.reset_input_buffer()
        s.write(cmd_qid)
        r_qid = s.read_until(b'\r', size=50)
        print(f"QID   : {r_qid}")
        
        # QPIGS
        time.sleep(0.2)
        cmd_qpigs = b'QPIGS' + crc16_voltronic(b'QPIGS') + b'\r'
        s.reset_input_buffer()
        s.write(cmd_qpigs)
        r_qpigs = s.read_until(b'\r', size=150)
        print(f"QPIGS : {r_qpigs}")
        
        # QPIGS2
        time.sleep(0.2)
        cmd_qpigs2 = b'QPIGS2' + crc16_voltronic(b'QPIGS2') + b'\r'
        s.reset_input_buffer()
        s.write(cmd_qpigs2)
        r_qpigs2 = s.read_until(b'\r', size=150)
        print(f"QPIGS2: {r_qpigs2}")
        
        s.close()
    except Exception as e:
        print(f"Error on {port}: {e}")
