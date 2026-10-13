#!/usr/bin/env python3
"""
Plots execution time, RAM usage, and network data exchanged, all vs.
number of issuers N, with a shaded +/-1 standard deviation band across
repeated runs (see sweep_issuer_metrics.py), instead of a single-run-
per-N curve.
"""
import argparse
import csv
import glob
import os
import re
import statistics
from collections import defaultdict

import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description="Plot execution time / RAM / network volume vs. N, with std bands")
parser.add_argument("--logs_dir", type=str, default="./logs")
parser.add_argument("--ram_volume_csv", type=str, default="./logs/ram_volume_sweep.csv")
parser.add_argument("--out_prefix", type=str, default="./logs/issuer_sweep")
args = parser.parse_args()

# --- Execution time: one CSV per N, accumulated across repeats -----------
time_by_n = {}
for path in glob.glob(os.path.join(args.logs_dir, "N*", "results.csv")):
    m = re.search(r"N(\d+)[\\/]results\.csv$", path)
    if not m:
        continue
    n = int(m.group(1))
    with open(path, newline="") as f:
        times = [float(row["time"]) for row in csv.DictReader(f)]
    if times:
        time_by_n[n] = times

# --- RAM and network volume: single consolidated CSV ---------------------
ram_by_n = defaultdict(list)
vol_by_n = defaultdict(list)
out_by_n = defaultdict(list)
in_by_n = defaultdict(list)
with open(args.ram_volume_csv, newline="") as f:
    for row in csv.DictReader(f):
        n = int(row["n_signers"])
        if row["mean_ram_mb"]:
            ram_by_n[n].append(float(row["mean_ram_mb"]))
        if row["mean_volume_kb"]:
            vol_by_n[n].append(float(row["mean_volume_kb"]))
        if row.get("mean_outbound_kb"):
            out_by_n[n].append(float(row["mean_outbound_kb"]))
        if row.get("mean_inbound_kb"):
            in_by_n[n].append(float(row["mean_inbound_kb"]))


def mean_and_std(values):
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


COLOR = "tab:blue"


def plot_on_axis(ax, by_n, ylabel):
    ns = sorted(by_n.keys())
    means, stds = zip(*(mean_and_std(by_n[n]) for n in ns))
    ax.plot(ns, means, color=COLOR)
    ax.fill_between(ns, [m - s for m, s in zip(means, stds)], [m + s for m, s in zip(means, stds)],
                     color=COLOR, alpha=0.25, linewidth=0)
    ax.set_xlabel("Number of issuers (N)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)


def plot_individual(by_n, ylabel, out_path):
    fig, ax = plt.subplots(figsize=(6, 5))
    plot_on_axis(ax, by_n, ylabel)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    print(f"Figure saved to {out_path}")


def plot_volume_breakdown(out_by_n, in_by_n, ylabel, out_path):
    ns = sorted(set(out_by_n.keys()) & set(in_by_n.keys()))
    fig, ax = plt.subplots(figsize=(6, 5))
    for by_n, label, color in [(out_by_n, "Outbound", COLOR), (in_by_n, "Inbound", "tab:orange")]:
        means, stds = zip(*(mean_and_std(by_n[n]) for n in ns))
        ax.plot(ns, means, color=color, label=label)
        ax.fill_between(ns, [m - s for m, s in zip(means, stds)], [m + s for m, s in zip(means, stds)],
                         color=color, alpha=0.25, linewidth=0)
    ax.set_xlabel("Number of issuers (N)")
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    print(f"Figure saved to {out_path}")


plot_individual(time_by_n, "Execution time (s)", f"{args.out_prefix}_time.png")
plot_individual(ram_by_n, "Memory usage (MB) per individual issuer", f"{args.out_prefix}_ram.png")
if out_by_n and in_by_n:
    plot_volume_breakdown(out_by_n, in_by_n, "Network data (KB) exchanged per individual issuer",
                           f"{args.out_prefix}_volume.png")
else:
    plot_individual(vol_by_n, "Network data (KB) exchanged per individual issuer", f"{args.out_prefix}_volume.png")
