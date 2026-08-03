import os
import glob

def main():
    print("=" * 60)
    print("      DEEP KERNEL USB DRIVER INSPECTOR (0665:5161)      ")
    print("=" * 60)

    usb_devices = sorted(glob.glob('/sys/bus/usb/devices/*'))
    found = 0

    for dev in usb_devices:
        id_vendor_file = os.path.join(dev, "idVendor")
        id_product_file = os.path.join(dev, "idProduct")

        if os.path.exists(id_vendor_file) and os.path.exists(id_product_file):
            try:
                with open(id_vendor_file) as f:
                    vid = f.read().strip()
                with open(id_product_file) as f:
                    pid = f.read().strip()

                if vid == "0665" and pid == "5161":
                    found += 1
                    dev_name = os.path.basename(dev)
                    product = ""
                    if os.path.exists(os.path.join(dev, "product")):
                        with open(os.path.join(dev, "product")) as pf:
                            product = pf.read().strip()

                    print(f"\n[+] Inverter Device #{found} at USB sysfs: {dev_name} ({dev})")
                    print(f"    Product     : {product}")

                    # Check interface subdirectories for drivers & dev nodes
                    intfs = glob.glob(os.path.join(dev, f"{dev_name}:*"))
                    for intf in intfs:
                        driver_link = os.path.join(intf, "driver")
                        driver_name = os.path.basename(os.readlink(driver_link)) if os.path.exists(driver_link) else "Unbound / None"
                        print(f"    Interface   : {os.path.basename(intf)} | Driver: {driver_name}")

                        # Check for tty or hidraw children
                        tty_nodes = glob.glob(os.path.join(intf, "tty*")) + glob.glob(os.path.join(intf, "tty", "tty*"))
                        hid_nodes = glob.glob(os.path.join(intf, "hidraw", "hidraw*"))
                        if tty_nodes:
                            print(f"      -> Serial TTY Nodes : {[os.path.basename(t) for t in tty_nodes]}")
                        if hid_nodes:
                            print(f"      -> HIDRAW Nodes     : {[os.path.basename(h) for h in hid_nodes]}")
            except Exception as e:
                pass

    if found == 0:
        print("[!] No 0665:5161 devices found in /sys/bus/usb/devices/")

if __name__ == "__main__":
    main()
