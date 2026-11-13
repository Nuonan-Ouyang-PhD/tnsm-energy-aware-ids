"""Read-only Linux interval CPU monitor; preserves every interval on stdout.

This is a preflight tool until integrated continuously in a new worker. The
threshold is conservative and is not a measured meter-noise equivalence bound.
"""
import argparse
import json
import os
from pathlib import Path
import time

from core import external_busy_fraction

LIMIT = .05  # Fraction of aggregate CPU capacity, not one-core percentage.


def cpu_ticks():
    fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:9]
    ticks = list(map(int, fields))
    return {"total": sum(ticks), "idle": ticks[3]+ticks[4]}


def process_stat(path):
    text = path.read_text()
    end = text.rindex(")")
    values = text[end+2:].split()
    return {"starttime": int(values[19]), "ppid": int(values[1]),
            "cpu_ticks": int(values[11])+int(values[12]),
            "comm": text[text.index("(")+1:end]}


def snapshot(roots=None):
    roots = {os.getpid()} if roots is None else set(roots)
    # Bracket only the explicitly allowed process counters with CPU totals.
    # Scanning every /proc entry between them caused wide, non-atomic windows
    # in the first retained calibration attempt. Keep attribution scans separate.
    begin = cpu_ticks()
    accounted = {pid: process_stat(Path(f"/proc/{pid}/stat")) for pid in roots}
    end = cpu_ticks()
    accounting_time = time.monotonic()
    processes = {}
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            processes[int(path.parent.name)] = process_stat(path)
        except ProcessLookupError:
            continue
        except FileNotFoundError:
            continue
        # Permission/parse errors are not silently ignored.
    return {"monotonic": accounting_time, "total": end["total"],
            "idle": end["idle"], "processes": processes,
            "accounting": {"begin": begin, "end": end, "roots": accounted}}


def allowed_tree(processes, roots):
    allowed = set(roots)
    while True:
        children = {pid for pid, p in processes.items() if p["ppid"] in allowed}
        updated = allowed | children
        if updated == allowed:
            return allowed
        allowed = updated


def interval(left, right, roots):
    before, after = left["processes"], right["processes"]
    if "accounting" in left and "accounting" in right:
        a, b = left["accounting"], right["accounting"]
        if set(a["roots"]) != set(roots) or set(b["roots"]) != set(roots):
            raise ValueError("CPU accounting roots changed")
        allowed_ticks = 0
        for pid in roots:
            if a["roots"][pid]["starttime"] != b["roots"][pid]["starttime"]:
                raise ValueError("allowed PID reused")
            delta = b["roots"][pid]["cpu_ticks"] - a["roots"][pid]["cpu_ticks"]
            if delta < 0:
                raise ValueError("allowed process counter reversed")
            allowed_ticks += delta
        # Conservative upper bound, accounting for non-atomic counter reads.
        total_low = b["begin"]["total"] - a["end"]["total"]
        busy_high = (b["end"]["total"] - b["end"]["idle"]) - (a["begin"]["total"] - a["begin"]["idle"])
        if total_low <= 0:
            raise ValueError("CPU accounting intervals overlap")
        fraction = max(0, busy_high - allowed_ticks) / total_low
        unrelated = []
        for pid, proc in after.items():
            old = before.get(pid)
            if pid not in roots and old and old["starttime"] == proc["starttime"]:
                delta = proc["cpu_ticks"]-old["cpu_ticks"]
                if delta > 0:
                    unrelated.append({"pid": pid, "starttime": proc["starttime"],
                                      "comm": proc["comm"], "cpu_ticks": delta})
        return {"external_busy_fraction": fraction, "limit": LIMIT,
                "pass": fraction <= LIMIT, "allowed_pids": sorted(roots),
                "unrelated_cpu": sorted(unrelated, key=lambda p: -p["cpu_ticks"]),
                "accounting": "conservative_upper_bound_bracketed_root_counters",
                "total_ticks_lower_bound": total_low, "busy_ticks_upper_bound": busy_high,
                "allowed_process_ticks": allowed_ticks}
    # Historical/synthetic snapshots without bracketing retain their old
    # descriptive arithmetic. Live snapshots above always use bounded readings.
    for pid in roots:
        if pid not in before or pid not in after or before[pid]["starttime"] != after[pid]["starttime"]:
            raise ValueError("allowed process disappeared or PID was reused")
    allowed = allowed_tree(after, roots)
    allowed_ticks = 0
    deltas = []
    for pid, proc in after.items():
        old = before.get(pid)
        if old is None or old["starttime"] != proc["starttime"]:
            continue
        delta = proc["cpu_ticks"]-old["cpu_ticks"]
        if delta < 0:
            raise ValueError("process CPU counter reversed")
        if pid in allowed:
            allowed_ticks += delta
        elif delta:
            deltas.append({"pid": pid, "starttime": proc["starttime"],
                           "comm": proc["comm"], "cpu_ticks": delta})
    fraction = external_busy_fraction(total_ticks=right["total"]-left["total"],
                    idle_ticks=right["idle"]-left["idle"],
                    allowed_process_ticks=allowed_ticks)
    return {"external_busy_fraction": fraction, "limit": LIMIT,
            "pass": fraction <= LIMIT,
            "unrelated_cpu": sorted(deltas, key=lambda p: -p["cpu_ticks"]),
            "allowed_pids": sorted(allowed)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()
    if args.seconds < 1:
        raise ValueError("positive monitoring period required")
    print(json.dumps({"event": "identity", "hostname": os.uname().nodename,
                      "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                      "monitor_pid": os.getpid(), "limit": LIMIT}), flush=True)
    left = snapshot()
    valid = True
    for i in range(args.seconds):
        time.sleep(1)
        right = snapshot()
        result = interval(left, right, {os.getpid()})
        valid = valid and result["pass"]
        print(json.dumps({"event": "cpu_interval", "index": i, **result,
                          "left": left, "right": right}), flush=True)
        left = right
    print(json.dumps({"event": "preflight_only_complete", "pass": valid,
                      "formal_run_authorized_by_this_check": False}), flush=True)
    return 0 if valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
