from serial_reader import serial_reader

has_alias = hasattr(serial_reader, "send_command")
has_setting = hasattr(serial_reader, "set_inverter_setting")

print(f"SerialInverterReader method check: send_command={has_alias}, set_inverter_setting={has_setting}")
