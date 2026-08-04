import sys
import logging
from hid_reader import HIDInverterReader

def main():
    logging.basicConfig(level=logging.INFO)
    reader = HIDInverterReader()
    print("\n--- Scanning & Mapping Devices ---")
    reader.scan_and_map_devices()
    print(f"Mapped Devices: {reader.mapped_devices}\n")

    print("--- Polling Live Telemetry ---")
    telemetry_all = reader.get_telemetry_for_selection("all")
    print(f"ALL Telemetry Output: {telemetry_all}\n")

    telemetry_inv1 = reader.get_telemetry_for_selection("inv1")
    print(f"INV1 Telemetry Output: {telemetry_inv1}\n")

    telemetry_inv2 = reader.get_telemetry_for_selection("inv2")
    print(f"INV2 Telemetry Output: {telemetry_inv2}\n")

    telemetry_inv3 = reader.get_telemetry_for_selection("inv3")
    print(f"INV3 Telemetry Output: {telemetry_inv3}\n")

if __name__ == "__main__":
    main()
