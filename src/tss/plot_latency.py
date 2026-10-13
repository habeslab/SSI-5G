#!/usr/bin/env python3
"""
Plots the VC issuance execution time as a function of the number of
issuers N, with one line per inter-issuer link latency L, from the CSV
produced by issuer_mininet.py / net_issuers.py.

Unlike a plot of time vs. N at L=0 only (i.e. same-host issuers), here
each latency value gets its own curve, so that both the effect of N
and of network latency (and their interaction) are visible.
"""
import argparse
import csv
import os
from collections import defaultdict

import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description="Plot VC issuance time vs. number of issuers, per link latency")
parser.add_argument("--csv", type=str,
                     default=os.getenv("ISSUER_LATENCY_RESULTS_CSV", "./logs/latency_results.csv"),
                     help="Path of the CSV file produced by the latency sweep")
parser.add_argument("--out", type=str, default="./logs/latency_results.png",
                     help="Path of the output figure")
parser.add_argument("--logy", action="store_true",
                     help="Use a logarithmic scale on the y-axis (useful given the wide time range)")
parser.add_argument("--baseline_csv", type=str, default=None,
                     help="Optional CSV produced by issuer_baseline.py: its single row (n_signers=1) "
                          "is drawn as a horizontal dashed reference line for the traditional "
                          "single-issuer scheme")
args = parser.parse_args()

series = defaultdict(list)  # latency_ms -> [(n_signers, time), ...]
with open(args.csv, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        n = int(float(row["n_signers"]))
        latency = float(row["latency_ms"])
        t = float(row["time"])
        series[latency].append((n, t))

fig, ax = plt.subplots(figsize=(7, 5))

for latency in sorted(series.keys()):
    points = sorted(series[latency])
    ns = [p[0] for p in points]
    times = [p[1] for p in points]
    ax.plot(ns, times, marker="o", label=f"L = {latency:.0f} ms")

if args.baseline_csv:
    with open(args.baseline_csv, newline="") as f:
        reader = csv.DictReader(f)
        baseline_time = float(next(reader)["time"])
    ax.axhline(baseline_time, color="black", linestyle="--", linewidth=1.5,
               label=f"Single issuer (baseline): {baseline_time * 1000:.2f} ms")

ax.set_xlabel("Number of issuers (N)")
ax.set_ylabel("Execution time (s)")
if args.logy:
    ax.set_yscale("log")
ax.set_xticks(sorted({n for points in series.values() for n, _ in points}))
ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)
ax.legend(title="Inter-issuer link latency")
fig.tight_layout()

os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
fig.savefig(args.out, dpi=300)
print(f"Figure saved to {args.out}")
