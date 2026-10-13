#!/usr/bin/env python3
"""
Scalability experiment: launches M UEs concurrently against a single
Network SSI Verifier + Authorization Server pair (the same Cloud RAN
topology as net.py), for increasing M, and measures how the system
behaves under concurrent load (success rate, per-UE latency, aggregate
throughput) rather than just replaying a single UE registration M times.

This exercises the verifier's concurrent-session support (see
communication.ConcurrentVerifierSocket / verifier.handle_ue): the plain
REP-based verifier used to only be able to carry one UE's multi-message
session at a time, so a second UE connecting mid-session would have
corrupted the first UE's protocol state. The ROUTER-based verifier
introduced for this experiment demultiplexes UEs by their ZMQ identity
and runs one thread per UE, so M UEs can be authenticated in parallel.
"""
import os
import re
import csv
import time
import statistics

from dotenv import load_dotenv

import net

load_dotenv()

N_UES_LIST = [int(x) for x in os.getenv("SCALABILITY_UE_LIST", "1,5,10,20,50").split(",")]
RESULTS_CSV = os.getenv("SCALABILITY_RESULTS_CSV", "./logs/scalability_results.csv")
WAIT_TIMEOUT_S = int(os.getenv("SCALABILITY_WAIT_TIMEOUT", "60"))
N_REPEATS = int(os.getenv("SCALABILITY_N_REPEATS", "1"))

ELAPSED_RE = re.compile(r"Elapsed time: ([0-9.eE+-]+)\. Communication volume")
FIELDNAMES = ["n_ues", "success_rate", "wall_time_s", "throughput_auth_per_s",
              "mean_latency_s", "p95_latency_s"]


def user_log_path(ue_id):
    return f"./logs/user_{ue_id}.log"


def clear_stale_logs(n_ues):
    # A previous, larger run may have left behind logs for UE ids that
    # this run does not use; stale files would otherwise be mistaken for
    # completed UEs of the current run if ids are reused.
    for i in range(n_ues):
        path = user_log_path(i)
        if os.path.exists(path):
            os.remove(path)


def start_all_ues(mn, n_ues, c_bbu_ip):
    for i in range(n_ues):
        net.start_ssi_user(mn.get(f"ue{i}"), c_bbu_ip, ue_id=i)


def wait_for_completion(n_ues, timeout_s):
    deadline = time.time() + timeout_s
    done = set()
    while time.time() < deadline and len(done) < n_ues:
        for i in range(n_ues):
            if i in done:
                continue
            path = user_log_path(i)
            if os.path.exists(path):
                with open(path) as f:
                    if "m6 received and decrypted successfully" in f.read():
                        done.add(i)
        if len(done) < n_ues:
            time.sleep(0.2)
    return done


def parse_elapsed(ue_id):
    with open(user_log_path(ue_id)) as f:
        match = ELAPSED_RE.search(f.read())
    return float(match.group(1)) if match else None


def percentile(values, pct):
    if not values:
        return float("nan")
    values = sorted(values)
    k = (len(values) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def run_one_config(n_ues):
    net.N_UEs = n_ues
    clear_stale_logs(n_ues)

    mn = net.create_cloud_ran()
    try:
        mn.start()
        net.start_authz_server(mn.get("authz"))
        c_bbu = mn.get("c_bbu")
        net.start_ssi_verifier(c_bbu)
        time.sleep(1)  # let the verifier/authz server processes come up

        wall_start = time.perf_counter()
        start_all_ues(mn, n_ues, c_bbu.IP())
        done = wait_for_completion(n_ues, WAIT_TIMEOUT_S)
        wall_time = time.perf_counter() - wall_start

        elapsed_times = [t for t in (parse_elapsed(i) for i in done) if t is not None]
        success_rate = len(elapsed_times) / n_ues

        return {
            "n_ues": n_ues,
            "success_rate": success_rate,
            "wall_time_s": wall_time,
            "throughput_auth_per_s": len(elapsed_times) / wall_time if wall_time > 0 else 0.0,
            "mean_latency_s": statistics.mean(elapsed_times) if elapsed_times else float("nan"),
            "p95_latency_s": percentile(elapsed_times, 0.95),
        }
    finally:
        mn.stop()


def append_row(row):
    # Opened and closed fresh for each row (rather than held open across
    # the whole sweep): each run_one_config() call starts and stops a
    # full Mininet network, whose low-level process/fd handling has been
    # observed to interfere with file descriptors held open by the
    # parent process across that boundary, silently losing buffered
    # writes. Writing one row per open/close cycle is slightly less
    # efficient but avoids relying on a long-lived file handle Mininet
    # doesn't know about, and persists each result immediately.
    file_exists = os.path.isfile(RESULTS_CSV)
    with open(RESULTS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())


def main():
    os.makedirs("./logs", exist_ok=True)
    print(f"Results will be appended to {os.path.abspath(RESULTS_CSV)}")

    for n_ues in N_UES_LIST:
        for repeat in range(1, N_REPEATS + 1):
            print(f"\n=== N_UEs = {n_ues} (repeat {repeat}/{N_REPEATS}) ===")
            row = run_one_config(n_ues)
            print(row)
            append_row(row)

    print(f"\nAll runs completed. Results saved to {RESULTS_CSV}")


if __name__ == "__main__":
    main()
