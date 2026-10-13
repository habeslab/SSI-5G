#!/usr/bin/env python3
"""
Plots per-UE authentication latency as a function of the number of
concurrently connecting UEs (M), from the CSV produced by
net_scalability.py. Each M value may have several repeated runs (see
net_scalability.py's SCALABILITY_N_REPEATS); the line shows the
across-run mean, with a shaded band of +/-1 standard deviation
indicating run-to-run variability. Points where success_rate < 1.0 (some
UEs did not complete within the wait timeout) are marked distinctly,
since they indicate the concurrent-session capacity limit of the
verifier has been reached rather than a steady-state measurement.
"""
import argparse
import csv
import os
import statistics
from collections import defaultdict

import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description="Plot per-UE latency vs. concurrent UEs, across repeated runs")
parser.add_argument("--csv", type=str,
                     default=os.getenv("SCALABILITY_RESULTS_CSV", "./logs/scalability_results.csv"))
parser.add_argument("--out", type=str, default="./logs/scalability_latency.png")
args = parser.parse_args()

by_n = defaultdict(lambda: {"mean": [], "p95": [], "success_rate": []})
with open(args.csv, newline="") as f:
    for row in csv.DictReader(f):
        n = int(row["n_ues"])
        by_n[n]["mean"].append(float(row["mean_latency_s"]) * 1000)
        by_n[n]["p95"].append(float(row["p95_latency_s"]) * 1000)
        by_n[n]["success_rate"].append(float(row["success_rate"]))

ns = sorted(by_n.keys())


def mean_and_band(values):
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


fig, ax = plt.subplots(figsize=(7, 5))

for label, key, color in [("mean", "mean", "tab:blue"), ("p95", "p95", "tab:orange")]:
    means, stds = zip(*(mean_and_band(by_n[n][key]) for n in ns))
    ax.plot(ns, means, marker="o", color=color, label=label)
    lower = [m - s for m, s in zip(means, stds)]
    upper = [m + s for m, s in zip(means, stds)]
    ax.fill_between(ns, lower, upper, color=color, alpha=0.2, linewidth=0)

avg_success = {n: statistics.mean(by_n[n]["success_rate"]) for n in ns}
partial_ns = [n for n in ns if avg_success[n] < 1.0]
for n in partial_ns:
    y = statistics.mean(by_n[n]["mean"])
    ax.annotate(f"{avg_success[n]*100:.0f}% completed", (n, y),
                textcoords="offset points", xytext=(-10, -15), color="tab:red", fontsize=9)
    ax.scatter([n], [y], color="tab:red", marker="x", s=100, zorder=4)

ax.set_xlabel("Concurrent UEs (M)")
ax.set_ylabel("Per-UE latency (ms)")
ax.set_title("SSI handshake latency vs. concurrent UEs (shaded: ±1 std across runs)")
ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
ax.legend()

fig.tight_layout()
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
fig.savefig(args.out, dpi=300)
print(f"Figure saved to {args.out}")
