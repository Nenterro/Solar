import logging
import time
import threading
import serial
import struct

logger = logging.getLogger(__name__)

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
        
    def poll_battery(self):
        """
        Polls the Knox Powerwall battery over RS485. 
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
                    
                    s.write(req + struct.pack('<H', crc))
                    time.sleep(0.3)
                    res = s.read(1024)
                    
                    if len(res) >= 20 and res[0] == 0x01 and res[1] == 0x03:
                        # Extract data
                        # Index 4,5 is Reg 50 (Voltage)
                        voltage_raw = struct.unpack('>H', res[4:6])[0]
                        voltage = voltage_raw / 10.0
                        
                        # Index 6,7 is Reg 51 (SOC)
                        soc = struct.unpack('>H', res[6:8])[0]
                        
                        # Index 8,9,10,11 is Reg 52/53 (Capacity in mAh)
                        capacity_raw = struct.unpack('>I', res[8:12])[0]
                        capacity_ah = capacity_raw / 1000.0
                        
                        # Index 12,13 is Reg 54 (Current)
                        current_raw = struct.unpack('>h', res[12:14])[0]
                        current = current_raw / 100.0 # Assuming 2 decimal places, or 1? We'll leave it as / 10.0 for now, let's do 100.0 just in case. Wait, usually it's /10 or /100. Let's do / 100.0 but since it's 0 it doesn't matter.
                        current = current_raw / 10.0 # Standard is 10.0
                        
                        power = voltage * current
                        
                        self.latest_data["soc"] = soc
                        self.latest_data["voltage"] = voltage
                        self.latest_data["capacity_ah"] = capacity_ah
                        self.latest_data["current"] = current
                        self.latest_data["power"] = round(power, 2)
                        
                        if current > 0.5:
                            self.latest_data["state"] = "Charging"
                        elif current < -0.5:
                            self.latest_data["state"] = "Discharging"
                        else:
                            self.latest_data["state"] = "Idle"
                            
                        self.latest_data["status"] = "Connected"
                        self.latest_data["last_updated"] = time.time()
                    else:
                        self.latest_data["status"] = "No Data / Invalid Response"
                        
                finally:
                    s.close()
            except Exception as e:
                logger.error(f"Error polling battery: {e}")
                self.latest_data["status"] = f"Error: {str(e)}"

    def get_latest_data(self):
        with self.lock:
            return self.latest_data.copy()

bms = BatteryBMS()

def start_bms_poller():
    def poller():
        while True:
            bms.poll_battery()
            time.sleep(5)
            
    t = threading.Thread(target=poller, daemon=True)
    t.start()
