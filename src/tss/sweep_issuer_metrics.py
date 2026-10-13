#!/usr/bin/env python3
"""
Repeats issuer.py's key-generation + signing experiment across N (number
of issuers) and multiple repeats, adding run-to-run variability (for a
shaded std band) to the execution-time, RAM-usage, and network-volume
vs. N figures already in the paper.

issuer.py already accumulates execution time across repeated invocations
in logs/N{N}/results.csv (append mode). RAM (per-node psrecord log) and
network volume (per-node Go CSV), however, are overwritten on every
invocation, so this script reads them immediately after each issuer.py
run -- averaging across the N nodes of that run -- and appends one row
per (N, repeat) to logs/ram_volume_sweep.csv.
"""
import csv
import os
import statistics
import subprocess
import sys

N_LIST = [int(x) for x in os.getenv("ISSUER_N_LIST_FULL", ",".join(str(n) for n in range(2, 41))).split(",")]
N_REPEATS = int(os.getenv("ISSUER_SWEEP_REPEATS", "3"))
OUT_CSV = os.getenv("ISSUER_RAM_VOLUME_CSV", "./logs/ram_volume_sweep.csv")


def mean_node_ram_mb(n):
    per_node_means = []
    for i in range(1, n + 1):
        path = f"./logs/N{n}/node_{i}_usage.log"
        if not os.path.isfile(path):
            continue
        values = []
        with open(path) as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    values.append(float(parts[2]))  # Real (MB)
        if values:
            per_node_means.append(statistics.mean(values))
    return statistics.mean(per_node_means) if per_node_means else None


def mean_node_volume_kb(n):
    values, out_values, in_values = [], [], []
    for i in range(1, n + 1):
        path = f"./logs/N{n}/volumes/node_{i}_volume.csv"
        if not os.path.isfile(path):
            continue
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                values.append(float(row["volume_bytes"]) / 1024)
                if row.get("outbound_bytes"):
                    out_values.append(float(row["outbound_bytes"]) / 1024)
                if row.get("inbound_bytes"):
                    in_values.append(float(row["inbound_bytes"]) / 1024)
    total = statistics.mean(values) if values else None
    outbound = statistics.mean(out_values) if out_values else None
    inbound = statistics.mean(in_values) if in_values else None
    return total, outbound, inbound


def main():
    os.makedirs("./logs", exist_ok=True)
    file_exists = os.path.isfile(OUT_CSV)
    with open(OUT_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["n_signers", "mean_ram_mb", "mean_volume_kb", "mean_outbound_kb", "mean_inbound_kb"])

        for n in N_LIST:
            for repeat in range(1, N_REPEATS + 1):
                print(f"=== N={n} (repeat {repeat}/{N_REPEATS}) ===", flush=True)
                subprocess.run([sys.executable, "issuer.py", "--n_signers", str(n)], check=True)
                ram = mean_node_ram_mb(n)
                vol, outbound, inbound = mean_node_volume_kb(n)
                writer.writerow([n, ram, vol, outbound, inbound])
                f.flush()
                print(f"  mean_ram_mb={ram}, mean_volume_kb={vol}, out={outbound}, in={inbound}", flush=True)


if __name__ == "__main__":
    main()
