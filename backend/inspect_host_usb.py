import glob
import os
import sys

def main():
    print("=" * 60)
    print("        LINUX HOST USB & HID DEVICE INSPECTOR        ")
    print("=" * 60)

    hidraws = sorted(glob.glob('/dev/hidraw*'))
    ttys = sorted(glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))

    print(f"\n[+] Found {len(hidraws)} /dev/hidraw device node(s):")
    for h in hidraws:
        # Check permissions / access
        readable = os.access(h, os.R_OK)
        writable = os.access(h, os.W_OK)
        print(f"  - {h:18s} | Read: {readable} | Write: {writable}")

    print(f"\n[+] Found {len(ttys)} Serial tty device node(s):")
    for t in ttys:
        print(f"  - {t:18s}")

if __name__ == "__main__":
    main()
