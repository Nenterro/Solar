import logging
import time
import threading
import serial
import struct
import glob

logger = logging.getLogger(__name__)

fast_poll_active = False

# Guards the poller singleton below.
_poller_lock = threading.Lock()
_poller_started = False


def modbus_crc(data: bytes) -> bytes:
    """Standard Modbus RTU CRC-16 (poly 0xA001), returned little-endian."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return struct.pack('<H', crc)


def _read_registers_frame() -> bytes:
    """Modbus request for 10 holding registers starting at 50, on slave 1."""
    req = bytearray(struct.pack('>BBHH', 1, 3, 50, 10))
    return bytes(req) + modbus_crc(req)

class BatteryBMS:
    def __init__(self, port="/dev/ttyUSB3", baudrate=9600):
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

    def _find_bms_port(self) -> str:
        """
        Auto-detect the Knox BMS RS485 port among the available USB serial devices.

        The probe used to build its request with a broken CRC (one shift per byte
        instead of the eight the Modbus polynomial needs), so no BMS ever replied
        and discovery could never succeed. It also has to hold the inverter
        reader's port lock: the candidate list includes the inverter ports, and
        probing one at 9600 baud mid-poll corrupts that poll.
        """
        candidate_ports = sorted(glob.glob('/dev/ttyUSB*'))
        if self.port in candidate_ports:
            candidate_ports.remove(self.port)
            candidate_ports.insert(0, self.port)

        full_cmd = _read_registers_frame()

        try:
            from serial_reader import serial_reader as _inverter_reader
            port_lock = _inverter_reader.serial_lock
        except Exception:
            port_lock = threading.Lock()

        with port_lock:
            for p in candidate_ports:
                try:
                    s = serial.Serial(p, self.baudrate, timeout=0.8)
                    try:
                        s.reset_input_buffer()
                        s.write(full_cmd)
                        time.sleep(0.15)
                        res = s.read(1024)
                    finally:
                        s.close()
                    if self._valid_response(res):
                        logger.info(f"Auto-detected Knox BMS RS485 on port {p}")
                        self.port = p
                        return p
                except Exception:
                    pass
        return self.port

    @staticmethod
    def _valid_response(res: bytes) -> bool:
        """
        Accept a BMS reply only if it is addressed correctly and long enough.

        The Knox BMS reports the register count where Modbus expects a byte
        count, so the frame length cannot be derived from the header and the
        trailing CRC cannot be located reliably. Header and length are therefore
        all that can be checked here; the value-range checks in poll_battery are
        what catch a corrupt payload.
        """
        return bool(res) and len(res) >= 20 and res[0] == 0x01 and res[1] == 0x03

    def poll_battery(self):
        """
        Polls the Knox Powerwall battery over RS485 with up to 3 retries.
        Uses raw pyserial because the Knox BMS has a Modbus RTU bug
        where it returns the register count instead of byte count in the header.
        """
        with self.lock:
            try:
                # 1. Try current port or auto-detect if necessary
                full_cmd = _read_registers_frame()

                success = False
                ports_to_try = [self.port]

                for target_port in ports_to_try:
                    try:
                        s = serial.Serial(target_port, self.baudrate, timeout=1.0)
                        try:
                            for attempt in range(3):
                                s.reset_input_buffer()
                                s.write(full_cmd)
                                time.sleep(0.2)
                                res = s.read(1024)

                                if self._valid_response(res):
                                    voltage_raw = struct.unpack('>H', res[4:6])[0]
                                    voltage = voltage_raw / 10.0
                                    soc_raw = struct.unpack('>H', res[6:8])[0]
                                    capacity_raw = struct.unpack('>I', res[8:12])[0]
                                    capacity_ah = capacity_raw / 1000.0
                                    current_raw = struct.unpack('>h', res[12:14])[0]
                                    current = current_raw / 10.0

                                    if soc_raw > 100 or soc_raw < 0 or voltage > 70.0 or voltage < 35.0:
                                        time.sleep(0.15)
                                        continue

                                    now_t = time.time()
                                    if self.last_valid_soc is not None and (now_t - getattr(self, 'last_soc_time', 0)) < 300:
                                        if abs(soc_raw - self.last_valid_soc) > 5.0:
                                            logger.warning(f"BMS RS485 attempt {attempt+1} SOC glitch rejected: {soc_raw}% vs last valid {self.last_valid_soc}%. Retrying...")
                                            time.sleep(0.15)
                                            continue

                                    power = voltage * current
                                    self.latest_data["soc"] = int(soc_raw)
                                    self.latest_data["voltage"] = voltage
                                    self.latest_data["capacity_ah"] = capacity_ah
                                    self.latest_data["current"] = current
                                    self.latest_data["power"] = round(power, 2)

                                    self.last_valid_soc = int(soc_raw)
                                    self.last_soc_time = now_t
                                    self.last_valid_voltage = voltage

                                    if current > 0.5:
                                        self.latest_data["state"] = "Charging"
                                    elif current < -0.5:
                                        self.latest_data["state"] = "Discharging"
                                    else:
                                        self.latest_data["state"] = "Idle"

                                    self.latest_data["status"] = "Connected"
                                    self.latest_data["last_updated"] = time.time()
                                    success = True
                                    return
                                else:
                                    time.sleep(0.15)
                        finally:
                            s.close()
                    except Exception:
                        pass

                # If primary port failed, attempt auto-discovery once
                if not success:
                    found_port = self._find_bms_port()
                    if found_port != self.port:
                        logger.info(f"Retrying poll on newly discovered Knox BMS port: {found_port}")

                self.latest_data["status"] = "No Data / Invalid Response"
                if self.last_valid_soc is not None:
                    self.latest_data["soc"] = self.last_valid_soc
                if self.last_valid_voltage is not None:
                    self.latest_data["voltage"] = self.last_valid_voltage

            except Exception as e:
                logger.error(f"Error polling battery: {e}")
                self.latest_data["status"] = f"Error: {str(e)}"
                if self.last_valid_soc is not None:
                    self.latest_data["soc"] = self.last_valid_soc
                if self.last_valid_voltage is not None:
                    self.latest_data["voltage"] = self.last_valid_voltage

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
    """
    Start the background BMS poller exactly once per process.

    This is called from both the FastAPI startup hook and the telemetry loop.
    Without the guard each call spawned another thread, so two pollers competed
    for the same RS485 port for the life of the process.
    """
    global _poller_started
    with _poller_lock:
        if _poller_started:
            return
        _poller_started = True

    def poller():
        while True:
            poll_start = time.time()
            try:
                bms.poll_battery()
            except Exception as e:
                logger.error(f"Unhandled error in BMS poller: {e}")

            # Poll every second only while someone is actually watching the
            # dashboard; otherwise once a minute is plenty.
            sleep_time = 1 if fast_poll_active else 60
            elapsed = time.time() - poll_start
            time.sleep(max(0.1, sleep_time - elapsed))

    threading.Thread(target=poller, daemon=True, name="bms-poller").start()
    logger.info("Knox BMS RS485 poller started")
