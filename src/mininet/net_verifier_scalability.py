#!/usr/bin/env python3
"""
Tests whether horizontally scaling the Network SSI Verifier resolves the
concurrency ceiling observed in net_scalability.py (throughput collapse
and success-rate drop between M=50 and M=100 concurrent UEs, traced to a
single, GIL-bound verifier process).

For a fixed number of concurrent UEs M, V independent verifier processes
are started (each a separate OS process, and therefore each with its own
GIL, unlike per-session threads within one process), listening on
consecutive ports on the same BBU host; UEs are distributed round-robin
across them. A single, shared Authorization Server is used throughout,
since it was not the bottleneck in the single-verifier experiment.
"""
import os
import re
import csv
import time
import statistics

from dotenv import load_dotenv

import net

load_dotenv()

FIXED_M = int(os.getenv("SCALABILITY_FIXED_M", "100"))
V_LIST = [int(x) for x in os.getenv("VERIFIER_COUNT_LIST", "1,2,4").split(",")]
RESULTS_CSV = os.getenv("VERIFIER_SCALABILITY_RESULTS_CSV", "./logs/verifier_scalability_results.csv")
WAIT_TIMEOUT_S = int(os.getenv("SCALABILITY_WAIT_TIMEOUT", "180"))
VERIFIER_PORT_BASE = int(os.getenv("VERIFIER_PORT"))
N_REPEATS = int(os.getenv("SCALABILITY_N_REPEATS", "1"))

ELAPSED_RE = re.compile(r"Elapsed time: ([0-9.eE+-]+)\. Communication volume")
FIELDNAMES = ["n_verifiers", "n_ues", "success_rate", "wall_time_s", "throughput_auth_per_s",
              "mean_latency_s", "p95_latency_s"]


def user_log_path(ue_id):
    return f"./logs/user_{ue_id}.log"


def clear_stale_logs(n_ues):
    for i in range(n_ues):
        path = user_log_path(i)
        if os.path.exists(path):
            os.remove(path)


def start_all_verifiers(mn, n_verifiers):
    c_bbu = mn.get("c_bbu")
    for v in range(n_verifiers):
        net.start_ssi_verifier(c_bbu, verifier_port=VERIFIER_PORT_BASE + v)
    return c_bbu


def start_all_ues(mn, n_ues, n_verifiers, c_bbu_ip):
    for i in range(n_ues):
        verifier_port = VERIFIER_PORT_BASE + (i % n_verifiers)
        net.start_ssi_user(mn.get(f"ue{i}"), c_bbu_ip, ue_id=i, verifier_port=verifier_port)


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


def run_one_config(n_verifiers, n_ues):
    net.N_UEs = n_ues
    clear_stale_logs(n_ues)

    mn = net.create_cloud_ran()
    try:
        mn.start()
        net.start_authz_server(mn.get("authz"))
        c_bbu = start_all_verifiers(mn, n_verifiers)
        time.sleep(1)

        wall_start = time.perf_counter()
        start_all_ues(mn, n_ues, n_verifiers, c_bbu.IP())
        done = wait_for_completion(n_ues, WAIT_TIMEOUT_S)
        wall_time = time.perf_counter() - wall_start

        elapsed_times = [t for t in (parse_elapsed(i) for i in done) if t is not None]
        success_rate = len(elapsed_times) / n_ues

        return {
            "n_verifiers": n_verifiers,
            "n_ues": n_ues,
            "success_rate": success_rate,
            "wall_time_s": wall_time,
            "throughput_auth_per_s": len(elapsed_times) / wall_time if wall_time > 0 else 0.0,
            "mean_latency_s": statistics.mean(elapsed_times) if elapsed_times else float("nan"),
            "p95_latency_s": percentile(elapsed_times, 0.95),
        }
    finally:
        mn.stop()


def main():
    os.makedirs("./logs", exist_ok=True)
    file_exists = os.path.isfile(RESULTS_CSV)
    with open(RESULTS_CSV, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()

        for n_verifiers in V_LIST:
            for repeat in range(1, N_REPEATS + 1):
                print(f"\n=== N_verifiers = {n_verifiers}, M = {FIXED_M} (repeat {repeat}/{N_REPEATS}) ===")
                row = run_one_config(n_verifiers, FIXED_M)
                print(row)
                writer.writerow(row)
                f.flush()

    print(f"\nAll runs completed. Results saved to {RESULTS_CSV}")


if __name__ == "__main__":
    main()
