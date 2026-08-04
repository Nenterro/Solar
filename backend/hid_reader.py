import os
import glob
import time
import logging
from typing import Dict, Any, List, Optional
import db

try:
    import serial
except ImportError:
    serial = None

logger = logging.getLogger("HID_READER")

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
        db.init_db()

    def send_cmd_to_node(self, node_path: str, cmd: str) -> Optional[str]:
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
        except Exception:
            return None

    def poll_serial_ports(self) -> Dict[str, Dict[str, Any]]:
        """Poll active RS232 / USB-Serial ports (/dev/ttyUSB*) for inverter telemetry."""
        if not serial:
            return {}

        ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
        if not ports:
            return {}

        readings = {}
        for port in ports:
            try:
                ser = serial.Serial(port, 2400, timeout=1.0)
                ser.reset_input_buffer()
                ser.reset_output_buffer()

                # Try parallel query QPGS0, QPGS1, QPGS2
                for idx, cfg in enumerate(INVERTERS_CONFIG):
                    inv_id = cfg["id"]
                    cmd = f"QPGS{idx}"
                    crc = crc16_voltronic(cmd)
                    ser.write(cmd.encode('ascii') + crc + b'\r')
                    time.sleep(0.15)
                    resp_b = ser.read(256)
                    if resp_b and b'(' in resp_b:
                        resp_str = resp_b.decode('ascii', errors='ignore')
                        idx_paren = resp_str.find('(')
                        if idx_paren != -1:
                            try:
                                parsed = self.parse_qpigs(resp_str[idx_paren:], inv_id)
                                readings[inv_id] = parsed
                                db.update_realtime(inv_id, parsed)
                            except Exception:
                                pass

                # Fallback to single QPIGS if parallel query returns empty
                if not readings:
                    cmd = "QPIGS"
                    crc = crc16_voltronic(cmd)
                    ser.write(cmd.encode('ascii') + crc + b'\r')
                    time.sleep(0.15)
                    resp_b = ser.read(256)
                    if resp_b and b'(' in resp_b:
                        resp_str = resp_b.decode('ascii', errors='ignore')
                        idx_paren = resp_str.find('(')
                        if idx_paren != -1:
                            try:
                                parsed = self.parse_qpigs(resp_str[idx_paren:], "inv1")
                                readings["inv1"] = parsed
                                db.update_realtime("inv1", parsed)
                            except Exception:
                                pass

                ser.close()
            except Exception as e:
                logger.debug(f"Serial port poll exception on {port}: {e}")

        return readings

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
        successful_reads = 0

        # 1. Try HID nodes first if present
        for cfg in INVERTERS_CONFIG:
            inv_id = cfg["id"]
            node_path = self.device_map.get(inv_id)

            if node_path and os.path.exists(node_path):
                for attempt in range(2):
                    qpigs_resp = self.send_cmd_to_node(node_path, "QPIGS")
                    if qpigs_resp:
                        try:
                            data = self.parse_qpigs(qpigs_resp, inv_id)
                            if data["ac_output_power_kw"] <= 25.0 and data["solar_power_kw"] <= 25.0:
                                self.readings_cache[inv_id] = data
                                db.update_realtime(inv_id, data)
                                successful_reads += 1
                                break
                        except Exception:
                            time.sleep(0.2)
                    else:
                        time.sleep(0.2)

        # 2. Try Serial ports (/dev/ttyUSB*) if HID reads were unsuccessful
        if successful_reads < len(INVERTERS_CONFIG):
            serial_readings = self.poll_serial_ports()
            for inv_id, data in serial_readings.items():
                self.readings_cache[inv_id] = data
                successful_reads += 1

        # 3. Fallback state for any unreadable inverter
        for cfg in INVERTERS_CONFIG:
            inv_id = cfg["id"]
            if inv_id not in self.readings_cache:
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

    def get_readings(self) -> Dict[str, Dict[str, Any]]:
        return self.poll_all_inverters()

hid_reader = HIDInverterReader()
