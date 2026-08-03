import os
import sys
import time

def bind_usbhid():
    print("=" * 60)
    print("     USB HID DRIVER RE-BINDER & USBFS TESTER     ")
    print("=" * 60)

    devices_to_bind = ["1-5:1.0", "1-9:1.0"]

    for dev in devices_to_bind:
        unbind_path = "/sys/bus/usb/drivers/usbfs/unbind"
        bind_path = "/sys/bus/usb/drivers/usbhid/bind"

        print(f"\n[+] Processing USB device {dev}...")

        # 1. Unbind from usbfs if bound
        try:
            if os.path.exists(unbind_path):
                with open(unbind_path, "w") as f:
                    f.write(dev)
                print(f"  [+] Unbound {dev} from usbfs driver")
        except Exception as u_err:
            print(f"  [-] Unbind note: {u_err}")

        # 2. Bind to usbhid
        try:
            if os.path.exists(bind_path):
                with open(bind_path, "w") as f:
                    f.write(dev)
                print(f"  [+] Successfully bound {dev} to usbhid driver!")
        except Exception as b_err:
            print(f"  [!] Bind note: {b_err}")

    time.sleep(1)
    # Check new hidraw nodes
    import glob
    nodes = sorted(glob.glob('/dev/hidraw*'))
    print(f"\n[+] Updated hidraw nodes in system: {nodes}")

if __name__ == "__main__":
    bind_usbhid()
