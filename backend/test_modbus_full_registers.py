import serial
import glob
import time
import sys

def main():
    port = "/dev/ttyUSB0"
    print(f"=== READING EXTENDED MODBUS REGISTERS ON {port} ===", flush=True)

    for baud in [2400, 9600]:
        try:
            ser = serial.Serial(port, baud, timeout=1.0)
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # Read 30 holding registers starting at 0x0000 (Func 3)
            mb_req = b"\x01\x03\x00\x00\x00\x1e\xc4\x0e"
            ser.write(mb_req)
            time.sleep(0.3)
            res = ser.read(256)

            if res and len(res) >= 5 and res[1] in (3, 4):
                byte_cnt = res[2] if res[2] != 0 else res[3]
                data_start = 3 if res[2] != 0 else 4
                regs = []
                for k in range(0, byte_cnt, 2):
                    if data_start + k + 1 < len(res):
                        val = (res[data_start + k] << 8) | res[data_start + k + 1]
                        regs.append(val)
                print(f"\n[BAUD {baud} Func 3 Regs 0-29] ({len(regs)} regs):", flush=True)
                for idx, v in enumerate(regs):
                    print(f"  Reg {idx:02d} (0x{idx:02X}): {v} (0x{v:04X})", flush=True)

            # Read 30 input registers starting at 0x0000 (Func 4)
            mb_req4 = b"\x01\x04\x00\x00\x00\x1e\x70\x0e"
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(mb_req4)
            time.sleep(0.3)
            res4 = ser.read(256)

            if res4 and len(res4) >= 5 and res4[1] in (3, 4):
                byte_cnt = res4[2] if res4[2] != 0 else res4[3]
                data_start = 3 if res4[2] != 0 else 4
                regs4 = []
                for k in range(0, byte_cnt, 2):
                    if data_start + k + 1 < len(res4):
                        val = (res4[data_start + k] << 8) | res4[data_start + k + 1]
                        regs4.append(val)
                print(f"\n[BAUD {baud} Func 4 Regs 0-29] ({len(regs4)} regs):", flush=True)
                for idx, v in enumerate(regs4):
                    print(f"  Reg {idx:02d} (0x{idx:02X}): {v} (0x{v:04X})", flush=True)

            ser.close()
        except Exception as e:
            print(f"Error @ {baud}: {e}", flush=True)

if __name__ == "__main__":
    main()
