import os
import glob
import sys

def main():
    print("=" * 60)
    print("      CHECKING FOR BUSY / LOCKED USB DEVICE NODES      ")
    print("=" * 60)

    # Check /dev/hidraw* nodes
    nodes = sorted(glob.glob('/dev/hidraw*'))
    print(f"\nTesting open() on hidraw nodes:")

    for node in nodes:
        try:
            fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
            os.close(fd)
            print(f"  [+] {node:15s} -> UNLOCKED (Successfully opened & closed)")
        except Exception as e:
            print(f"  [!] {node:15s} -> LOCKED / BUSY ({e})")

if __name__ == "__main__":
    main()
