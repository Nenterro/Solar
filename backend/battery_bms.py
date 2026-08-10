import logging
import time
import threading
import serial
import struct

logger = logging.getLogger(__name__)

fast_poll_active = False

class BatteryBMS:
    def __init__(self, port="/dev/ttyUSB0", baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.lock = threading.Lock()
        
        # Cache for the latest battery state
        self.latest_data = {
            "soc": 0,
            "voltage": 0.0,
            "current": 0.0,
            "power": 0.0,
            "temperature": 0.0,
            "capacity_ah": 0.0,
            "state": "Unknown",
            "last_updated": None,
            "status": "Disconnected"
        }
        self.last_valid_soc = None
        self.last_valid_voltage = None
        
    def poll_battery(self):
        """
        Polls the Knox Powerwall battery over RS485 with up to 3 retries.
        Uses raw pyserial because the Knox BMS has a Modbus RTU bug 
        where it returns the register count instead of byte count in the header.
        """
        with self.lock:
            try:
                s = serial.Serial(self.port, self.baudrate, timeout=1.0)
                try:
                    # Query 10 registers starting at 50 (0x0032)
                    # Reg 50 = Voltage, Reg 51 = SOC, Reg 52/53 = Capacity
                    req = bytearray(struct.pack('>BBHH', 1, 3, 50, 10))
                    crc = 0xFFFF
                    for b in req:
                        crc ^= b
                        for _ in range(8):
                            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
                    
                    full_cmd = req + struct.pack('<H', crc)

                    for attempt in range(3):
                        s.reset_input_buffer()
                        s.write(full_cmd)
                        time.sleep(0.2)
                        res = s.read(1024)

                        if len(res) >= 20 and res[0] == 0x01 and res[1] == 0x03:
                            # Extract data
                            voltage_raw = struct.unpack('>H', res[4:6])[0]
                            voltage = voltage_raw / 10.0
                            soc_raw = struct.unpack('>H', res[6:8])[0]
                            capacity_raw = struct.unpack('>I', res[8:12])[0]
                            capacity_ah = capacity_raw / 1000.0
                            current_raw = struct.unpack('>h', res[12:14])[0]
                            current = current_raw / 10.0

                            # Strict Bounds Validation for Knox BMS RS485 Response
                            if soc_raw > 100 or soc_raw < 0 or voltage > 70.0 or voltage < 35.0:
                                logger.warning(f"BMS RS485 attempt {attempt+1} invalid: SOC={soc_raw}%, V={voltage}V. Retrying...")
                                time.sleep(0.15)
                                continue

                            power = voltage * current
                            self.latest_data["soc"] = int(soc_raw)
                            self.latest_data["voltage"] = voltage
                            self.latest_data["capacity_ah"] = capacity_ah
                            self.latest_data["current"] = current
                            self.latest_data["power"] = round(power, 2)
                            
                            self.last_valid_soc = int(soc_raw)
                            self.last_valid_voltage = voltage
                            
                            if current > 0.5:
                                self.latest_data["state"] = "Charging"
                            elif current < -0.5:
                                self.latest_data["state"] = "Discharging"
                            else:
                                self.latest_data["state"] = "Idle"
                                
                            self.latest_data["status"] = "Connected"
                            self.latest_data["last_updated"] = time.time()
                            return # Successful poll
                        else:
                            time.sleep(0.15)

                    self.latest_data["status"] = "No Data / Invalid Response"

                finally:
                    s.close()
            except Exception as e:
                logger.error(f"Error polling battery: {e}")
                self.latest_data["status"] = f"Error: {str(e)}"

    def get_latest_data(self):
        with self.lock:
            data = self.latest_data.copy()
            if (data.get("soc", 0) == 0 or data.get("voltage", 0.0) == 0.0):
                if self.last_valid_soc is not None:
                    data["soc"] = self.last_valid_soc
                if self.last_valid_voltage is not None:
                    data["voltage"] = self.last_valid_voltage
            return data

bms = BatteryBMS()

def start_bms_poller():
    def poller():
        global fast_poll_active
        while True:
            poll_start = time.time()
            bms.poll_battery()
            
            sleep_time = 1 if fast_poll_active else 60
            elapsed = time.time() - poll_start
            time.sleep(max(0.1, sleep_time - elapsed))
            
    t = threading.Thread(target=poller, daemon=True)
    t.start()
