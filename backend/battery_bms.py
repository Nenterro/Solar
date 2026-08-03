import logging
import time
import threading
from pymodbus.client import ModbusSerialClient

logger = logging.getLogger(__name__)

class BatteryBMS:
    def __init__(self, port="/dev/ttyUSB0", baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.client = ModbusSerialClient(port=self.port, baudrate=self.baudrate, timeout=1)
        self.lock = threading.Lock()
        
        # Cache for the latest battery state
        self.latest_data = {
            "soc": 0,
            "voltage": 0.0,
            "current": 0.0,
            "power": 0.0,
            "temperature": 0.0,
            "state": "Unknown",
            "last_updated": None,
            "status": "Disconnected"
        }
        
    def poll_battery(self):
        """
        Polls the battery over RS485. 
        Currently supports generic PACE/Knox Modbus RTU at 9600 baud.
        """
        with self.lock:
            try:
                if not self.client.connect():
                    self.latest_data["status"] = "Connection Failed"
                    return
                
                # Attempt to read generic PACE Modbus registers
                try:
                    res = self.client.read_holding_registers(0, 32, slave=1)
                except Exception as e:
                    # Fallback for older pymodbus versions
                    res = self.client.read_holding_registers(0, 32, unit=1)
                    
                if not res.isError() and len(res.registers) >= 20:
                    # MOCK PARSING until manual confirms exact registers!
                    self.latest_data["soc"] = 85 # Placeholder
                    self.latest_data["voltage"] = 53.2
                    self.latest_data["current"] = 10.5
                    self.latest_data["power"] = round(53.2 * 10.5, 2)
                    self.latest_data["temperature"] = 25.0
                    self.latest_data["state"] = "Discharging"
                    self.latest_data["status"] = "Connected"
                    self.latest_data["last_updated"] = time.time()
                else:
                    self.latest_data["status"] = "No Data / Invalid Protocol"
                    
            except Exception as e:
                logger.error(f"Error polling battery: {e}")
                self.latest_data["status"] = f"Error: {str(e)}"
            finally:
                self.client.close()

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
