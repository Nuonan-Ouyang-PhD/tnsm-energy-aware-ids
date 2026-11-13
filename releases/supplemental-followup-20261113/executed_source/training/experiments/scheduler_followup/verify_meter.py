"""Bounded KM003C/Pi identity preflight; no inference or load generation."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

import hid

ROOT = Path(__file__).resolve().parents[2]
SERIAL = "075356"
PI_SERIAL = "100000005368e39d"
REMOTE = '''import json,socket,time,shutil,subprocess
from pathlib import Path
cpu=Path('/proc/cpuinfo').read_text()
print(json.dumps({'hostname':socket.gethostname(),'utc_epoch':time.time(),
'cpu_serial':next(x.split(':',1)[1].strip() for x in cpu.splitlines() if x.startswith('Serial')),
'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
'model':Path('/proc/device-tree/model').read_text().rstrip(chr(0)),
'temperature_c':int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000,
'throttled':subprocess.check_output(['vcgencmd','get_throttled'],text=True).strip(),
'ntp_synchronized':subprocess.check_output(['timedatectl','show','-p','NTPSynchronized','--value'],text=True).strip(),
'free_bytes':shutil.disk_usage('/').free,'load_1m':__import__('os').getloadavg()[0]}))
'''


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"status": "IN_PROGRESS", "scope": "READ_ONLY_IDENTITY_AND_IDLE_ADC_PREFLIGHT",
              "user_confirmed_inline_wiring": True,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "workload_started": False, "physical_experiment_runs": 0}
    device = None
    try:
        with (args.output.parent / "meter_access.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Use the exact archived decoder, after checking its frozen binding.
            source = ROOT / "revision_experiments_20260908/measurement.py"
            manifest = json.loads((source.parent / "runtime_manifest.json").read_text())
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if actual != manifest["files"]["measurement.py"]:
                raise RuntimeError("frozen ADC decoder hash mismatch")
            report["decoder_sha256"] = actual
            spec = importlib.util.spec_from_file_location("adc_decoder", source)
            decoder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(decoder)
            completed = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                                        "pi@pi4b8g.local", "python3 -"],
                                       input=REMOTE, capture_output=True, text=True, timeout=20)
            report["ssh_returncode"] = completed.returncode
            report["ssh_stderr"] = completed.stderr
            if completed.returncode:
                raise RuntimeError("Pi identity probe failed")
            pi = json.loads(completed.stdout)
            report["pi"] = pi
            if pi["hostname"] != "pi4b8g" or pi["cpu_serial"] != PI_SERIAL:
                raise RuntimeError("unexpected Pi identity")
            if "Raspberry Pi 4 Model B" not in pi["model"]:
                raise RuntimeError("unexpected Pi model")
            if pi["temperature_c"] >= 70 or pi["throttled"] != "throttled=0x0":
                raise RuntimeError("Pi thermal/throttle gate failed")
            if pi["ntp_synchronized"] != "yes" or pi["free_bytes"] < 1 << 30:
                raise RuntimeError("Pi clock/disk gate failed")
            candidates = [x for x in hid.enumerate(0x5fc9, 0x0063) if x.get("serial_number") == SERIAL]
            report["meter_interfaces"] = len(candidates)
            if not candidates:
                raise RuntimeError("expected meter not enumerated")
            device = hid.device()
            device.open(0x5fc9, 0x0063, SERIAL)
            report["opened_meter_serial"] = device.get_serial_number_string()
            if report["opened_meter_serial"] != SERIAL:
                raise RuntimeError("opened meter identity mismatch")
            samples = []
            with (args.output / "adc_samples.jsonl").open("x") as log:
                for index in range(10):
                    request = decoder.request(index)
                    sent = time.monotonic()
                    written = device.write(request)
                    if written != len(request):
                        raise RuntimeError("short HID request write")
                    raw = bytes(device.read(64, 1000))
                    received = time.monotonic()
                    values = decoder.decode(raw, index)
                    item = {"index": index, "utc": datetime.now(timezone.utc).isoformat(),
                            "request_monotonic": sent, "receive_monotonic": received,
                            "raw_hex": raw.hex(), **values}
                    log.write(json.dumps(item, allow_nan=False)+"\n")
                    log.flush()
                    samples.append(item)
                    if received - sent > .25:
                        raise RuntimeError("meter response exceeds timing gate")
                    if index != 9:
                        time.sleep(1)
            report.update(status="PASS", samples=len(samples),
                voltage_range_v=[min(x["volts"] for x in samples), max(x["volts"] for x in samples)],
                idle_power_range_w=[min(x["watts"] for x in samples), max(x["watts"] for x in samples)],
                interpretation="communication/identity/accepted campaign envelope only; not independent voltage calibration or proof of supply safety",
                formal_execution_unlocked=False)
    except Exception as error:
        report.update(status="FAIL_STOP_NO_RETRY", error=repr(error), formal_execution_unlocked=False)
    finally:
        if device is not None:
            device.close()
        save(args.output / "report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
