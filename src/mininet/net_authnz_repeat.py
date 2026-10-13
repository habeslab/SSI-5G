#!/usr/bin/env python3
"""
Repeats the single-UE authentication+authorization experiment (the one
behind Tables tab:autenticazione/tab:autorizzazione in the manuscript)
N_REPEATS times, restarting the Cloud RAN topology fresh each time (same
pattern as net_scalability.py), and records per-run execution time and
RAM usage for the UE, the Network SSI Verifier and the Authorization
Server, so that the tables can report mean +/- std instead of 3 manually
picked example runs.
"""
import os
import re
import csv
import time
import statistics

from dotenv import load_dotenv

import net

load_dotenv()

N_REPEATS = int(os.getenv("AUTHNZ_N_REPEATS", "15"))
RESULTS_CSV = os.getenv("AUTHNZ_RESULTS_CSV", "./logs/authnz_repeat_results.csv")
WAIT_TIMEOUT_S = int(os.getenv("AUTHNZ_WAIT_TIMEOUT", "60"))

USER_LOG = "./logs/user_0.log"
VERIFIER_LOG = "./logs/verifier.log"
AUTHZ_LOG = "./logs/authz_server.log"

USER_RE = re.compile(r"Elapsed time: ([0-9.eE+-]+)\. Communication volume: ([0-9.]+) KBs")
VERIFIER_SSI_RE = re.compile(r"Elapsed time for SSI: ([0-9.eE+-]+)\. \. Communication volume: ([0-9.]+) KBs")
VERIFIER_AUTHZ_RE = re.compile(r"Elapsed time for authorization: ([0-9.eE+-]+)")
AUTHZ_RE = re.compile(r"Elapsed time: ([0-9.eE+-]+)")

FIELDNAMES = [
    "repeat",
    "user_time_s", "user_volume_kb", "user_ram_mb",
    "verifier_ssi_time_s", "verifier_volume_kb", "verifier_authz_time_s", "verifier_ram_mb",
    "authz_time_s", "authz_ram_mb",
]


def clear_stale_logs():
    for path in [USER_LOG, VERIFIER_LOG, AUTHZ_LOG,
                 "./logs/ram_log_user_0.csv", "./logs/ram_log_verifier.csv", "./logs/ram_log_authz.csv"]:
        if os.path.exists(path):
            os.remove(path)


def wait_for_completion(timeout_s):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if os.path.exists(USER_LOG):
            with open(USER_LOG) as f:
                if "m6 received and decrypted successfully" in f.read():
                    return True
        time.sleep(0.2)
    return False


def wait_for_match(path, regex, timeout_s=10):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if os.path.exists(path):
            with open(path) as f:
                m = regex.search(f.read())
                if m:
                    return m
        time.sleep(0.2)
    return None


def mean_ram_mb(role):
    path = f"./logs/ram_log_{role}.csv"
    if not os.path.isfile(path):
        return None
    values = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                values.append(float(row["ram_MB"]))
            except (KeyError, ValueError):
                continue
    return statistics.mean(values) if values else None


def run_one_repeat():
    net.N_UEs = 1
    clear_stale_logs()

    mn = net.create_cloud_ran()
    try:
        mn.start()
        net.start_authz_server(mn.get("authz"))
        c_bbu = mn.get("c_bbu")
        net.start_ssi_verifier(c_bbu)
        time.sleep(1)  # let the verifier/authz server processes come up

        net.start_ssi_user(mn.get("ue0"), c_bbu.IP(), ue_id=0)

        if not wait_for_completion(WAIT_TIMEOUT_S):
            raise RuntimeError("UE did not complete registration in time")

        user_m = wait_for_match(USER_LOG, USER_RE)
        verifier_ssi_m = wait_for_match(VERIFIER_LOG, VERIFIER_SSI_RE)
        verifier_authz_m = wait_for_match(VERIFIER_LOG, VERIFIER_AUTHZ_RE)
        authz_m = wait_for_match(AUTHZ_LOG, AUTHZ_RE)

        if not (user_m and verifier_ssi_m and verifier_authz_m and authz_m):
            raise RuntimeError("Could not parse all expected log lines")

        return {
            "user_time_s": float(user_m.group(1)),
            "user_volume_kb": float(user_m.group(2)),
            "user_ram_mb": mean_ram_mb("user_0"),
            "verifier_ssi_time_s": float(verifier_ssi_m.group(1)),
            "verifier_volume_kb": float(verifier_ssi_m.group(2)),
            "verifier_authz_time_s": float(verifier_authz_m.group(1)),
            "verifier_ram_mb": mean_ram_mb("verifier"),
            "authz_time_s": float(authz_m.group(1)),
            "authz_ram_mb": mean_ram_mb("authz"),
        }
    finally:
        mn.stop()


def append_row(row):
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

    for repeat in range(1, N_REPEATS + 1):
        print(f"\n=== Repeat {repeat}/{N_REPEATS} ===", flush=True)
        row = {"repeat": repeat}
        row.update(run_one_repeat())
        print(row, flush=True)
        append_row(row)

    print(f"\nAll runs completed. Results saved to {RESULTS_CSV}")


if __name__ == "__main__":
    main()
