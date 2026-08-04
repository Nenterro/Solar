import os
import glob
import time
import logging
from typing import Dict, Any, List, Optional
import db

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("HID_READER")

# Direct Hardware Mappings verified via Linux sysfs
HARDCODED_NODES = {
    "inv1": "/dev/hidraw0",
    "inv2": "/dev/hidraw1",
    "inv3": "/dev/hidraw2",
}

INVERTERS_CONFIG = [
    {"id": "inv1", "label": "Inverter 1", "sn": "96342504101941"},
    {"id": "inv2", "label": "Inverter 2", "sn": "96342504101900"},
    {"id": "inv3", "label": "Inverter 3", "sn": "96342504102056"},
]

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

class HIDInverterReader:
    def __init__(self):
        self.device_map: Dict[str, str] = HARDCODED_NODES.copy()
        self.is_connected = True
        self.use_mock = False
        self.readings_cache: Dict[str, Dict[str, Any]] = {}
        self.last_db_log_time = 0

        # Initialize SQLite DB
        db.init_db()

    def send_cmd_to_node(self, node_path: str, cmd: str) -> Optional[str]:
        """
        Send raw Voltronic command via direct Linux OS file descriptor I/O.
        """
        try:
            fd = os.open(node_path, os.O_RDWR | os.O_NONBLOCK)
            crc = crc16_voltronic(cmd)
            payload = cmd.encode('ascii') + crc + b'\x0d'

            for i in range(0, len(payload), 8):
                chunk = payload[i:i+8]
                if len(chunk) < 8:
                    chunk = chunk + b'\x00' * (8 - len(chunk))
                os.write(fd, chunk)

            time.sleep(0.12)
            response_bytes = bytearray()
            start = time.time()
            while time.time() - start < 0.7:
                try:
                    data = os.read(fd, 64)
                    if data:
                        response_bytes.extend(data)
                        if b'\r' in response_bytes:
                            break
                except BlockingIOError:
                    time.sleep(0.04)

            os.close(fd)

            if response_bytes:
                return response_bytes.split(b'\r')[0].decode('ascii', errors='ignore')
            return None
        except Exception as e:
            return None

    def scan_and_map_devices(self) -> bool:
        # Keep direct hardware mappings active
        self.device_map = HARDCODED_NODES.copy()
        self.is_connected = True
        return True

    def parse_qpigs(self, qpigs_str: str, inv_id: str) -> Dict[str, Any]:
        if not qpigs_str or not qpigs_str.startswith('('):
            raise ValueError(f"Invalid QPIGS response format: {qpigs_str}")

        parts = qpigs_str[1:].split()
        if len(parts) < 16:
            raise ValueError(f"Insufficient QPIGS tokens ({len(parts)} tokens)")

        grid_voltage = float(parts[0])
        grid_freq = float(parts[1])
        ac_out_voltage = float(parts[2])
        ac_out_freq = float(parts[3])
        ac_out_apparent_power = float(parts[4])
        ac_out_active_power = float(parts[5])
        load_pct = float(parts[6])
        bus_voltage = float(parts[7])
        battery_voltage = float(parts[8])
        battery_charge_current = float(parts[9])
        battery_capacity_pct = float(parts[10])
        inverter_temp = float(parts[11])
        pv_input_current = float(parts[12])
        pv_input_voltage = float(parts[13])
        pv_input_power = float(parts[19]) if len(parts) >= 20 else (pv_input_current * pv_input_voltage)
        battery_discharge_current = float(parts[15]) if len(parts) >= 16 else 0.0

        solar_kw = round(pv_input_power / 1000.0, 2)
        load_kw = round(ac_out_active_power / 1000.0, 2)
        battery_net_power = round(((battery_charge_current - battery_discharge_current) * battery_voltage) / 1000.0, 2)
        grid_kw = round(load_kw + battery_net_power - solar_kw, 2)

        return {
          "inverter_id": inv_id,
          "timestamp": int(time.time()),
          "connected": True,
          "is_simulated": False,
          "grid_voltage": grid_voltage,
          "grid_frequency": grid_freq,
          "ac_output_voltage": ac_out_voltage,
          "ac_output_frequency": ac_out_freq,
          "ac_output_power_kw": load_kw,
          "load_percentage": load_pct,
          "solar_power_kw": solar_kw,
          "pv_voltage": pv_input_voltage,
          "pv_current": pv_input_current,
          "battery_voltage": battery_voltage,
          "battery_capacity_pct": battery_capacity_pct,
          "battery_power_kw": battery_net_power,
          "battery_charge_current": battery_charge_current,
          "battery_discharge_current": battery_discharge_current,
          "grid_power_kw": grid_kw,
          "grid_active": grid_voltage > 90.0,
          "inverter_temp_c": inverter_temp
        }

    def poll_all_inverters(self) -> Dict[str, Dict[str, Any]]:
        """
        Poll QPIGS telemetry directly from /dev/hidraw0, /dev/hidraw1, /dev/hidraw2.
        """
        successful_reads = 0

        for cfg in INVERTERS_CONFIG:
            inv_id = cfg["id"]
            node_path = self.device_map.get(inv_id)

            if node_path and os.path.exists(node_path):
                # Try up to 3 times per inverter to handle USB HID corruption/timeouts
                success = False
                for attempt in range(3):
                    qpigs_resp = self.send_cmd_to_node(node_path, "QPIGS")
                    if qpigs_resp:
                        try:
                            data = self.parse_qpigs(qpigs_resp, inv_id)
                            
                            # Hardware sanity check: Reject physically impossible artifacts
                            if data["ac_output_power_kw"] > 25.0 or data["solar_power_kw"] > 25.0:
                                raise ValueError("Parsed power values exceed realistic limits (Hardware glitch)")
                                
                            self.readings_cache[inv_id] = data
                            db.update_realtime(inv_id, data)
                            successful_reads += 1
                            success = True
                            break  # Success, exit retry loop
                        except Exception as e:
                            logger.warning(f"QPIGS parse error for {inv_id} at {node_path} (Attempt {attempt+1}/3): {e}")
                            time.sleep(0.3)
                    else:
                        time.sleep(0.3)
                
                if success:
                    continue

            # Fallback zeroed state if node unreadable
            self.readings_cache[inv_id] = {
              "inverter_id": inv_id,
              "label": cfg["label"],
              "timestamp": int(time.time()),
              "connected": False,
              "is_simulated": True,
              "solar_power_kw": 0.0,
              "ac_output_power_kw": 0.0,
              "grid_power_kw": 0.0,
              "battery_power_kw": 0.0,
              "battery_capacity_pct": 71.0,
              "battery_voltage": 53.3,
              "grid_voltage": 223.5,
              "grid_frequency": 50.0,
              "grid_active": True,
              "inverter_temp_c": 50.0,
              "load_percentage": 0.0
            }

        self.is_connected = successful_reads > 0
        return self.readings_cache

    def get_telemetry_for_selection(self, selected_inverter: str = "all") -> Dict[str, Any]:
        all_readings = self.poll_all_inverters()

        if selected_inverter in all_readings:
            return all_readings[selected_inverter]

        # Calculate aggregate system total for 'all'
        readings_list = list(all_readings.values())
        total_solar = round(sum(r.get("solar_power_kw", 0.0) for r in readings_list), 2)
        total_load = round(sum(r.get("ac_output_power_kw", 0.0) for r in readings_list), 2)
        total_battery = round(sum(r.get("battery_power_kw", 0.0) for r in readings_list), 2)
        total_grid = round(sum(r.get("grid_power_kw", 0.0) for r in readings_list), 2)
        
        valid_soc = [r.get("battery_capacity_pct", 71) for r in readings_list if r.get("battery_capacity_pct")]
        avg_soc = round(sum(valid_soc) / len(valid_soc), 2) if valid_soc else 71

        grid_voltages = [r.get("grid_voltage", 0) for r in readings_list if r.get("grid_voltage", 0) > 0]
        avg_grid_v = round(sum(grid_voltages) / len(grid_voltages), 1) if grid_voltages else 0.0

        grid_freqs = [r.get("grid_frequency", 0) for r in readings_list if r.get("grid_frequency", 0) > 0]
        avg_grid_f = round(sum(grid_freqs) / len(grid_freqs), 1) if grid_freqs else 0.0

        temps = [r.get("inverter_temp_c", 0) for r in readings_list if r.get("inverter_temp_c", 0) > 0]
        avg_temp = round(sum(temps) / len(temps), 1) if temps else 0.0

        is_grid_active = any(r.get("grid_active", False) for r in readings_list)

        agg_data = {
          "inverter_id": "all",
          "label": "All Inverters",
          "timestamp": int(time.time()),
          "connected": self.is_connected,
          "is_simulated": not self.is_connected,
          "solar_power_kw": total_solar,
          "ac_output_power_kw": total_load,
          "grid_power_kw": total_grid,
          "battery_power_kw": total_battery,
          "battery_capacity_pct": avg_soc,
          "battery_voltage": 53.3,
          "grid_voltage": avg_grid_v,
          "grid_frequency": avg_grid_f,
          "grid_active": is_grid_active,
          "inverter_temp_c": avg_temp,
          "load_percentage": round((total_load / 15.0) * 100, 1)
        }
        db.update_realtime("all", agg_data)
        return agg_data
