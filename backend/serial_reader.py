import os
import glob
import time
import json
import logging
import threading
from typing import Dict, Any, List, Optional

try:
    import serial
except ImportError:
    serial = None

import db

logger = logging.getLogger("SERIAL_READER")

# Standard configuration for the dashboard
INVERTERS_CONFIG = [
    {"id": "inv1", "label": "Inverter 1", "sn": "96342504101941"},
    {"id": "inv2", "label": "Inverter 2", "sn": "96342504101900"},
    {"id": "inv3", "label": "Inverter 3", "sn": "96342504102056"},
]

def crc16_voltronic(data: bytes) -> bytes:
    crc = 0x0000
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF
    
    crc_high = (crc >> 8) & 0xFF
    crc_low = crc & 0xFF
    
    # Voltronic escapes certain CRCs
    if crc_high in (0x0A, 0x0D, 0x28):
        crc_high += 1
    if crc_low in (0x0A, 0x0D, 0x28):
        crc_low += 1
        
    return bytes([crc_high, crc_low])


class SerialInverterReader:
    def __init__(self):
        # We will attempt to automatically map USB ports based on their discovery order.
        # e.g., ttyUSB0 -> inv1, ttyUSB1 -> inv2, ttyUSB2 -> inv3
        self.device_map: Dict[str, str] = {}
        self.is_connected = True
        self.use_mock = False
        self._last_port_count = -1
        self.serial_lock = threading.Lock()
        self.readings_cache: Dict[str, Dict[str, Any]] = {}
        db.init_db()

    def parse_qpigs(self, qpigs_str: str, inv_id: str, qpigs2_str: Optional[str] = None) -> Dict[str, Any]:
        """Parse standard Voltronic QPIGS + QPIGS2 response (Knox Trio format)."""
        if not qpigs_str or not qpigs_str.startswith('('):
            raise ValueError(f"Invalid QPIGS response format: {qpigs_str}")

        parts = qpigs_str[1:].split()
        if len(parts) < 20:
            raise ValueError(f"Insufficient QPIGS tokens ({len(parts)} tokens)")

        # Standard Knox Trio mapping based on rigorous real-world testing
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
        battery_discharge_current = float(parts[15]) if len(parts) >= 16 else 0.0

        # Knox MPPT String 1 (PV1)
        pv1_w = float(parts[19]) if len(parts) >= 20 else (pv_input_current * pv_input_voltage)
        
        # Knox MPPT String 2 (PV2 from QPIGS2 command)
        pv2_current, pv2_voltage, pv2_w = 0.0, 0.0, 0.0
        if qpigs2_str and qpigs2_str.startswith('('):
            parts2 = qpigs2_str[1:].split()
            if len(parts2) >= 3:
                try:
                    pv2_current = float(parts2[0])
                    pv2_voltage = float(parts2[1])
                    pv2_w = float(parts2[2])
                except Exception:
                    pass

        # Total Solar Generation from both MPPT strings
        solar_kw = round((pv1_w + pv2_w) / 1000.0, 2)
        load_kw = round(ac_out_active_power / 1000.0, 2)
        battery_net_power = round(((battery_charge_current - battery_discharge_current) * battery_voltage) / 1000.0, 2)
        
        # Display PV Voltage & Current from active MPPT string
        effective_pv_voltage = pv_input_voltage if pv_input_voltage > 0 else pv2_voltage
        effective_pv_current = pv_input_current if pv_input_current > 0 else pv2_current

        # Net Grid Power: Positive = Importing from grid, Negative = Exporting / Feeding to grid
        grid_kw = round(load_kw + battery_net_power - solar_kw, 2)

        # Basic Sanity Bounds (Max 15kW per inverter, realistic voltages/temps)
        if abs(grid_kw) > 15.0 or abs(load_kw) > 15.0 or abs(solar_kw) > 15.0 or abs(battery_net_power) > 15.0:
            raise ValueError(f"Absurd power values (>15kW) detected, ignoring frame: {qpigs_str}")
            
        if battery_voltage > 70.0 or battery_voltage < 35.0:
            raise ValueError(f"Absurd battery voltage ({battery_voltage}V) detected, ignoring frame")
            
        if inverter_temp > 120.0 or inverter_temp < -20.0:
            raise ValueError(f"Absurd inverter temp ({inverter_temp}C) detected, ignoring frame")

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
          "pv_voltage": effective_pv_voltage,
          "pv_current": effective_pv_current,
          "battery_voltage": battery_voltage,
          "battery_capacity_pct": battery_capacity_pct,
          "battery_power_kw": battery_net_power,
          "battery_charge_current": battery_charge_current,
          "battery_discharge_current": battery_discharge_current,
          "grid_power_kw": grid_kw,
          "grid_import_kw": max(0.0, grid_kw),
          "grid_export_kw": abs(min(0.0, grid_kw)),
          "grid_active": grid_voltage > 90.0,
          "inverter_temp_c": inverter_temp
        }

    def poll_serial_ports(self) -> Dict[str, Dict[str, Any]]:
        """Poll active RS232 / USB-Serial ports (/dev/ttyUSB*) at 2400 baud."""
        if not serial:
            logger.error("PySerial not installed.")
            return {}

        with self.serial_lock:
            ports = sorted(glob.glob("/dev/ttyUSB*"))
            if not ports:
                return {}

            if not self.device_map or len(self.device_map) < 2 or len(ports) != getattr(self, '_last_port_count', -1):
                self._last_port_count = len(ports)
                self.device_map = {}
                qid_cmd = b'QID' + crc16_voltronic(b'QID') + b'\r'
                qpgs0_cmd = b'QPGS0' + crc16_voltronic(b'QPGS0') + b'\r'
                
                for port in ports:
                    try:
                        sn = None
                        s = serial.Serial(port, 2400, timeout=1.0)
                        
                        # 1. Try QID command
                        s.reset_input_buffer()
                        s.write(qid_cmd)
                        resp = s.read_until(b'\r', size=50)
                        if resp:
                            decoded = resp.decode('ascii', errors='ignore').strip()
                            if decoded.startswith('(') and len(decoded) >= 15:
                                sn = decoded[1:15]

                        # 2. Fallback to QPGS0 command if QID is unsupported or failed
                        if not sn:
                            time.sleep(0.15)
                            s.reset_input_buffer()
                            s.write(qpgs0_cmd)
                            resp = s.read_until(b'\r', size=150)
                            if resp:
                                decoded = resp.decode('ascii', errors='ignore').strip()
                                parts = decoded[1:].split() if decoded.startswith('(') else []
                                if len(parts) >= 2 and len(parts[1]) >= 10:
                                    sn = parts[1]

                        s.close()

                        if sn:
                            # Match SN to config
                            for cfg in INVERTERS_CONFIG:
                                if cfg["sn"] == sn:
                                    self.device_map[cfg["id"]] = port
                                    logger.info(f"Mapped {cfg['id']} ({cfg['sn']}) -> {port}")
                                    break
                    except Exception as e:
                        logger.debug(f"Error mapping port {port}: {e}")
                logger.info(f"Auto-mapped inverter ports based on Serial Number: {self.device_map}")

            readings = {}
            cmd_qpigs = b'QPIGS' + crc16_voltronic(b'QPIGS') + b'\r'
            cmd_qpigs2 = b'QPIGS2' + crc16_voltronic(b'QPIGS2') + b'\r'

            for inv_id, port in self.device_map.items():
                try:
                    ser = serial.Serial(port, 2400, timeout=1.5)
                    
                    for attempt in range(3):
                        ser.reset_input_buffer()
                        ser.write(cmd_qpigs)
                        resp1 = ser.read_until(b'\r', size=150)
                        
                        time.sleep(0.2)
                        ser.reset_input_buffer()
                        ser.write(cmd_qpigs2)
                        resp2 = ser.read_until(b'\r', size=150)
                        
                        d1 = resp1.decode('ascii', errors='ignore').strip() if resp1 else ""
                        d2 = resp2.decode('ascii', errors='ignore').strip() if resp2 else ""
                        
                        if d1 and d1.startswith('('):
                            try:
                                readings[inv_id] = self.parse_qpigs(d1, inv_id, d2)
                                break # Clean read successful
                            except Exception as parse_e:
                                time.sleep(0.2)
                                continue
                                
                    ser.close()
                        
                except Exception as e:
                    logger.error(f"Serial port exception on {port} ({inv_id}): {e}")

            return readings

    def poll_all_inverters(self) -> Dict[str, Dict[str, Any]]:
        successful_reads = 0

        # Poll real serial ports
        serial_readings = self.poll_serial_ports()
        for inv_id, data in serial_readings.items():
            self.readings_cache[inv_id] = data
            successful_reads += 1

        # Clear stale cache and set fallback for any inverter that did NOT respond this cycle.
        # This prevents old readings from persisting and creating phantom spikes in aggregation.
        for cfg in INVERTERS_CONFIG:
            inv_id = cfg["id"]
            if inv_id not in serial_readings:
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
                  "battery_capacity_pct": 0.0,
                  "battery_voltage": 0.0,
                  "grid_voltage": 0.0,
                  "grid_frequency": 0.0,
                  "grid_active": False,
                  "inverter_temp_c": 0.0,
                  "load_percentage": 0.0
                }

        self.is_connected = successful_reads > 0
        return self.readings_cache

    def get_readings(self) -> Dict[str, Dict[str, Any]]:
        if not self.readings_cache:
            return self.poll_all_inverters()
        return self.readings_cache

    def get_telemetry_for_selection(self, selected_inverter: str = "all") -> Dict[str, Any]:
        all_readings = self.get_readings()

        if selected_inverter in all_readings:
            return all_readings[selected_inverter]

        # Aggregate metrics for "all" selection
        readings_list = list(all_readings.values())
        total_solar = round(sum(r.get("solar_power_kw", 0.0) for r in readings_list), 2)
        total_load = round(sum(r.get("ac_output_power_kw", 0.0) for r in readings_list), 2)
        total_battery = round(sum(r.get("battery_power_kw", 0.0) for r in readings_list), 2)
        total_grid_import = round(sum(r.get("grid_import_kw", 0.0) for r in readings_list), 2)
        total_grid_export = round(sum(r.get("grid_export_kw", 0.0) for r in readings_list), 2)
        total_grid = round(sum(r.get("grid_power_kw", 0.0) for r in readings_list), 2)

        valid_soc = [r.get("battery_capacity_pct", 0) for r in readings_list if r.get("battery_capacity_pct")]
        avg_soc = round(sum(valid_soc) / len(valid_soc), 2) if valid_soc else 0.0

        valid_v = [r.get("battery_voltage", 0) for r in readings_list if r.get("battery_voltage", 0) > 0]
        avg_bat_v = round(sum(valid_v) / len(valid_v), 2) if valid_v else 0.0

        grid_voltages = [r.get("grid_voltage", 0) for r in readings_list if r.get("grid_voltage", 0) > 0]
        avg_grid_v = round(sum(grid_voltages) / len(grid_voltages), 1) if grid_voltages else 0.0

        grid_freqs = [r.get("grid_frequency", 0) for r in readings_list if r.get("grid_frequency", 0) > 0]
        avg_grid_f = round(sum(grid_freqs) / len(grid_freqs), 1) if grid_freqs else 0.0

        temps = [r.get("inverter_temp_c", 0) for r in readings_list if r.get("inverter_temp_c", 0) > 0]
        avg_temp = round(sum(temps) / len(temps), 1) if temps else 0.0

        return {
            "inverter_id": "all",
            "inverter_sn": "Knox Hybrid Trio System",
            "solar_power_kw": total_solar,
            "ac_output_power_kw": total_load,
            "grid_power_kw": total_grid,
            "grid_import_kw": total_grid_import,
            "grid_export_kw": total_grid_export,
            "battery_power_kw": total_battery,
            "battery_capacity_pct": avg_soc,
            "battery_voltage": avg_bat_v,
            "grid_voltage": avg_grid_v,
            "grid_frequency": avg_grid_f,
            "grid_active": avg_grid_v > 90.0,
            "inverter_temp_c": avg_temp,
            "status": "Normal",
            "work_mode": "Hybrid Parallel",
            "readings_count": len(readings_list)
        }

    def parse_total(self, data_str: str) -> float:
        """Parse Voltronic lifetime accumulated energy (10-digit 100Wh counter -> float kWh)."""
        try:
            import re
            match = re.match(r'^\((\d+)', data_str)
            if match:
                val_str = match.group(1)
                # Voltronic lifetime counters are 10-digit numbers in 100Wh units (0.1 kWh)
                val_raw = float(val_str)
                return round(val_raw / 100.0, 1)
        except Exception:
            pass
        return 0.0

    def poll_daily_totals(self) -> Dict[str, Dict[str, float]]:
        """Poll lifetime hardware energy registers (QET, QLT, QGT, QFT, QCT, QDT) from all connected inverters."""
        totals = {}
        
        cmds = {
            'solar': 'QET',
            'load': 'QLT',
            'grid_import': 'QGT',
            'grid_export': 'QFT',
            'battery_charge': 'QCT',
            'battery_discharge': 'QDT'
        }
        
        # Ensure mapping exists
        if not self.device_map:
            self.poll_serial_ports()
            
        with self.serial_lock:
            for inv_id, port in self.device_map.items():
                inv_totals = {}
                try:
                    ser = serial.Serial(port, 2400, timeout=1.0)
                    
                    for key, cmd in cmds.items():
                        cb = cmd.encode('ascii')
                        full_cmd = cb + crc16_voltronic(cb) + b'\r'
                        
                        parsed_val = 0.0
                        for attempt in range(3):
                            ser.reset_input_buffer()
                            ser.write(full_cmd)
                            
                            try:
                                resp = ser.read_until(b'\r', size=50)
                                if resp and resp.startswith(b'('):
                                    decoded = resp.decode('ascii', errors='ignore').strip()
                                    parsed_val = self.parse_total(decoded)
                                    break
                            except Exception:
                                time.sleep(0.15)
                                continue
                                
                        inv_totals[key] = parsed_val
                        time.sleep(0.05) # Brief pause between commands
                        
                    ser.close()
                except Exception as e:
                    logger.error(f"Error reading lifetime totals on {port} ({inv_id}): {e}")
                
                # Use 0.0 defaults if disconnected
                totals[inv_id] = inv_totals if inv_totals else {k: 0.0 for k in cmds.keys()}
            
        return totals

    def get_inverter_settings(self, inverter_id: str) -> Dict[str, Any]:
        """Query Output Source Priority, Feed to Grid, and Charger Source Priority settings."""
        if not self.device_map:
            self.poll_serial_ports()

        # If inverter_id is 'all', return list of settings for all connected inverters
        if inverter_id == "all":
            all_settings = {}
            for inv_key in self.device_map.keys():
                all_settings[inv_key] = self.get_inverter_settings(inv_key)
            return all_settings

        port = self.device_map.get(inverter_id)
        if not port:
            return {"error": f"Inverter '{inverter_id}' not connected"}

        with self.serial_lock:
            try:
                ser = serial.Serial(port, 2400, timeout=1.5)

                # 1. Query QPIRI (Rating & Settings Information)
                cb = b'QPIRI'
                ser.reset_input_buffer()
                ser.write(cb + crc16_voltronic(cb) + b'\r')
                qpiri_resp = ser.read_until(b'\r', size=150).decode('ascii', errors='ignore').strip()

                time.sleep(0.1)

                # 2. Query QFLAG (Enable/Disable Flags including Feed-to-Grid 'b')
                cb = b'QFLAG'
                ser.reset_input_buffer()
                ser.write(cb + crc16_voltronic(cb) + b'\r')
                qflag_resp = ser.read_until(b'\r', size=150).decode('ascii', errors='ignore').strip()

                ser.close()

                out_code = "0"
                charger_code = "0"
                machine_type = "0"
                feed_enabled = False
                
                v_back_grid = 52.0
                v_cutoff = 46.0
                v_bulk = 57.6
                v_float = 57.0
                v_back_disch = 54.0

                if qpiri_resp.startswith('('):
                    parts = qpiri_resp[1:].split()
                    if len(parts) >= 23:
                        machine_type = parts[12]
                        out_code = parts[16]
                        charger_code = parts[17]
                        try:
                            v_back_grid = float(parts[8])
                            v_cutoff = float(parts[9])
                            v_bulk = float(parts[10])
                            v_float = float(parts[11])
                            v_back_disch = float(parts[22])
                        except Exception:
                            pass

                # Parse Flag 'd' in QFLAG for Feed to Grid enable/disable
                if qflag_resp.startswith('('):
                    if 'D' in qflag_resp:
                        e_part = qflag_resp[1:].split('D')[0]
                    else:
                        e_part = qflag_resp[1:]
                    feed_enabled = 'd' in e_part

                out_labels = {'0': 'USB', '1': 'SUB', '2': 'SBU'}
                charger_labels = {'1': 'Solar First', '2': 'Solar and Utility', '3': 'Solar Only'}

                return {
                    "inverter_id": inverter_id,
                    "port": port,
                    "machine_type": "Hybrid Grid-Tie with Backup" if machine_type in ("2", "02") else f"Mode {machine_type}",
                    "output_source_priority": {
                        "code": out_code,
                        "label": out_labels.get(out_code, f"Unknown ({out_code})"),
                        "options": [
                            {"code": "0", "label": "USB", "cmd": "POP00"},
                            {"code": "1", "label": "SUB", "cmd": "POP01"},
                            {"code": "2", "label": "SBU", "cmd": "POP02"}
                        ]
                    },
                    "charging_source_priority": {
                        "code": charger_code,
                        "label": charger_labels.get(charger_code, f"Unknown ({charger_code})"),
                        "options": [
                            {"code": "1", "label": "Solar First", "cmd": "PCP01"},
                            {"code": "2", "label": "Solar and Utility", "cmd": "PCP02"},
                            {"code": "3", "label": "Solar Only", "cmd": "PCP03"}
                        ]
                    },
                    "feed_to_grid": {
                        "enabled": feed_enabled,
                        "label": "Enabled (Solar Grid Export Active)" if feed_enabled else "Disabled (No Grid Export)",
                        "enable_cmd": "PEd",
                        "disable_cmd": "PDd"
                    },
                    "voltage_thresholds": {
                        "back_to_grid_voltage": {
                            "value": v_back_grid,
                            "unit": "V",
                            "set_cmd_prefix": "PBCV"
                        },
                        "back_to_discharge_voltage": {
                            "value": v_back_disch,
                            "unit": "V",
                            "set_cmd_prefix": "PBDV"
                        },
                        "battery_cut_off_voltage": {
                            "value": v_cutoff,
                            "unit": "V",
                            "set_cmd_prefix": "PSDV"
                        },
                        "battery_voltage_turn_off_ac2": {
                            "value": 56.5,
                            "unit": "V",
                            "set_cmd_prefix": "PAC2OFF"
                        },
                        "battery_voltage_turn_on_ac2": {
                            "value": 57.0,
                            "unit": "V",
                            "set_cmd_prefix": "PAC2ON"
                        },
                        "bulk_charging_voltage": {
                            "value": v_bulk,
                            "unit": "V",
                            "set_cmd_prefix": "PCVV"
                        },
                        "float_charging_voltage": {
                            "value": v_float,
                            "unit": "V",
                            "set_cmd_prefix": "PBFT"
                        }
                    }
                }
            except Exception as e:
                logger.error(f"Error querying settings for {inverter_id}: {e}")
                return {"error": str(e)}

    def set_inverter_setting(self, inverter_id: str, command: str) -> Dict[str, Any]:
        """Send a configuration setting command to an inverter (e.g. POP01, PCP02, PEb, PDb)."""
        if not self.device_map:
            self.poll_serial_ports()

        port = self.device_map.get(inverter_id)
        if not port:
            return {"success": False, "detail": f"Inverter '{inverter_id}' not connected"}

        with self.serial_lock:
            try:
                ser = serial.Serial(port, 2400, timeout=2.0)
                cb = command.encode('ascii')
                full_cmd = cb + crc16_voltronic(cb) + b'\r'
                ser.reset_input_buffer()
                ser.write(full_cmd)
                resp = ser.read_until(b'\r', size=50)
                ser.close()

                if resp and b'ACK' in resp:
                    logger.info(f"Successfully applied setting '{command}' on {inverter_id} ({port}): ACK")
                    return {"success": True, "command": command, "response": "ACK"}
                else:
                    logger.warning(f"Setting command '{command}' on {inverter_id} returned: {resp}")
                    return {"success": False, "command": command, "response": resp.decode('ascii', errors='ignore')}
            except Exception as e:
                logger.error(f"Error setting command '{command}' on {inverter_id}: {e}")
                return {"success": False, "error": str(e)}

serial_reader = SerialInverterReader()
