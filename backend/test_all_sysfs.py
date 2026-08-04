import os
import glob

def find_hidraw_mappings():
    print("=" * 60)
    print("       LINUX SYSFS USB TO /dev/hidraw MAPPING SCANNER       ")
    print("=" * 60)

    hidraw_sys_paths = sorted(glob.glob('/sys/class/hidraw/hidraw*'))
    print(f"[+] Found {len(hidraw_sys_paths)} hidraw entries in sysfs:\n")

    for entry in hidraw_sys_paths:
        node_name = os.path.basename(entry)
        dev_node = f"/dev/{node_name}"
        
        # Read device uevent / uevent properties
        uevent_file = os.path.join(entry, "device", "uevent")
        modalias_file = os.path.join(entry, "device", "modalias")
        
        info = []
        if os.path.exists(uevent_file):
            with open(uevent_file, "r") as f:
                info = [line.strip() for line in f.readlines() if line.strip()]

        print(f"Node: {dev_node:15s} ({entry})")
        for line in info:
            if "HID_NAME" in line or "HID_ID" in line or "DEVNAME" in line or "PRODUCT" in line:
                print(f"  - {line}")
        print()

if __name__ == "__main__":
    find_hidraw_mappings()
