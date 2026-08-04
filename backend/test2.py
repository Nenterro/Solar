import sys
sys.path.append('.')
from hid_reader import HIDInverterReader
reader = HIDInverterReader()
print('QPIGS:', reader.send_cmd_to_node('/dev/hidraw0', 'QPIGS'))
print('QPGS0:', reader.send_cmd_to_node('/dev/hidraw0', 'QPGS0'))
print('QPGS1:', reader.send_cmd_to_node('/dev/hidraw0', 'QPGS1'))
