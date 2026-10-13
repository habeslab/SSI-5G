#!/usr/bin/env python3
"""
Plots authentication throughput at a fixed number of concurrent UEs (M)
as a function of the number of independent Network SSI Verifier
processes (V), from the CSV produced by net_verifier_scalability.py.
Each V value may have several repeated runs (see
net_verifier_scalability.py's SCALABILITY_N_REPEATS); the line shows the
across-run mean, with a shaded band of +/-1 standard deviation.
"""
import argparse
import csv
import os
import statistics
from collections import defaultdict

import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description="Plot throughput vs. number of verifier instances")
parser.add_argument("--csv", type=str,
                     default=os.getenv("VERIFIER_SCALABILITY_RESULTS_CSV", "./logs/verifier_scalability_results.csv"))
parser.add_argument("--out", type=str, default="./logs/verifier_scalability.png")
args = parser.parse_args()

by_v = defaultdict(lambda: {"throughput": [], "mean_latency": [], "success_rate": []})
fixed_m = None
with open(args.csv, newline="") as f:
    for row in csv.DictReader(f):
        v = int(row["n_verifiers"])
        fixed_m = int(row["n_ues"])
        by_v[v]["throughput"].append(float(row["throughput_auth_per_s"]))
        by_v[v]["mean_latency"].append(float(row["mean_latency_s"]) * 1000)
        by_v[v]["success_rate"].append(float(row["success_rate"]))

vs = sorted(by_v.keys())


def mean_and_std(values):
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

means, stds = zip(*(mean_and_std(by_v[v]["throughput"]) for v in vs))
ax1.plot(vs, means, marker="o", color="tab:blue")
ax1.fill_between(vs, [m - s for m, s in zip(means, stds)], [m + s for m, s in zip(means, stds)],
                  color="tab:blue", alpha=0.2, linewidth=0)
ax1.set_xlabel("Number of Verifier instances (V)")
ax1.set_ylabel("Throughput (auth/s)")
ax1.set_title(f"Authentication throughput vs. V (M = {fixed_m} concurrent UEs)")
ax1.set_xticks(vs)
ax1.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

means_l, stds_l = zip(*(mean_and_std(by_v[v]["mean_latency"]) for v in vs))
ax2.plot(vs, means_l, marker="o", color="tab:orange")
ax2.fill_between(vs, [m - s for m, s in zip(means_l, stds_l)], [m + s for m, s in zip(means_l, stds_l)],
                  color="tab:orange", alpha=0.2, linewidth=0)
ax2.set_xlabel("Number of Verifier instances (V)")
ax2.set_ylabel("Mean per-UE latency (ms)")
ax2.set_title(f"SSI handshake latency vs. V (M = {fixed_m} concurrent UEs)")
ax2.set_xticks(vs)
ax2.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

for v in vs:
    avg_success = statistics.mean(by_v[v]["success_rate"])
    if avg_success < 1.0:
        y = statistics.mean(by_v[v]["throughput"])
        ax1.annotate(f"{avg_success*100:.0f}% completed", (v, y),
                     textcoords="offset points", xytext=(-10, 10), color="tab:red", fontsize=9)
        ax1.scatter([v], [y], color="tab:red", marker="x", s=100, zorder=4)

fig.tight_layout()
os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
fig.savefig(args.out, dpi=300)
print(f"Figure saved to {args.out}")
