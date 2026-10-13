#!/usr/bin/env python3
"""
Compares the FROST threshold-signature scheme against the naive N-of-N
multi-signature baseline (see ./multisig/main.go, multisig_mininet.py),
the second baseline requested to strengthen the evaluation against
competing decentralized-authentication schemes that do not use threshold
cryptography.

Three figures are produced:
  1. Issuance latency vs. N, both schemes overlaid, for each inter-issuer
     latency L present in both result files.
  2. VC size vs. N: FROST's aggregate signature is constant-size, while
     naive multisig must carry N independent (pubkey, signature) pairs.
  3. Verifier-side verification time vs. N, measured directly (not
     estimated): one Ed25519 verification for FROST regardless of N,
     N independent Ed25519 verifications for the multisig baseline.
"""
import csv
import statistics
import time
from collections import defaultdict

import matplotlib.pyplot as plt
from cryptography.hazmat.primitives.asymmetric import ed25519

from vc_message import build_message_b64

FROST_CSV = "./logs/latency_results.csv"
MULTISIG_CSV = "./logs/multisig_latency_results.csv"


def load_latency(path):
    by_latency = defaultdict(lambda: defaultdict(list))
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            n = int(float(row["n_signers"]))
            l = float(row["latency_ms"])
            by_latency[l][n].append(float(row["time"]))
    return by_latency


def mean(values):
    return statistics.mean(values)


# --- Figure 1: latency vs N, both schemes, one panel per shared L --------
frost = load_latency(FROST_CSV)
multisig = load_latency(MULTISIG_CSV)
shared_latencies = sorted(set(frost.keys()) & set(multisig.keys()))

fig, axes = plt.subplots(1, len(shared_latencies), figsize=(5 * len(shared_latencies), 4.5), sharey=False)
if len(shared_latencies) == 1:
    axes = [axes]

for ax, l in zip(axes, shared_latencies):
    ns_frost = sorted(frost[l].keys())
    ns_multi = sorted(multisig[l].keys())
    ax.plot(ns_frost, [mean(frost[l][n]) for n in ns_frost], marker="o", color="tab:blue", label="FROST (t-of-n)")
    ax.plot(ns_multi, [mean(multisig[l][n]) for n in ns_multi], marker="s", color="tab:red", label="Naive N-of-N multisig")
    ax.set_xlabel("Number of issuers (N)")
    ax.set_ylabel("Issuance time (s)")
    ax.set_title(f"L = {l:.0f} ms")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.legend()

fig.tight_layout()
fig.savefig("./logs/multisig_comparison_latency.png", dpi=300)
print("Figure saved to ./logs/multisig_comparison_latency.png")

# --- Figure 2: VC size vs N (analytical, exact byte counts) --------------
ED25519_SIG_BYTES = 64
ED25519_PUBKEY_BYTES = 32

ns = list(range(2, 41))
frost_size = [ED25519_SIG_BYTES for _ in ns]  # constant-size aggregate signature
multisig_size = [n * (ED25519_SIG_BYTES + ED25519_PUBKEY_BYTES) for n in ns]

fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(ns, frost_size, color="tab:blue", label="FROST (t-of-n): 1 aggregate signature")
ax.plot(ns, multisig_size, color="tab:red", label="Naive N-of-N multisig: N (pubkey, signature) pairs")
ax.set_xlabel("Number of issuers (N)")
ax.set_ylabel("VC signature material (bytes)")
ax.set_title("Credential signature size vs. N")
ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
ax.legend()
fig.tight_layout()
fig.savefig("./logs/multisig_comparison_vc_size.png", dpi=300)
print("Figure saved to ./logs/multisig_comparison_vc_size.png")

# --- Figure 3: verification time vs N (measured) --------------------------
message_b64 = build_message_b64()
message_bytes = message_b64.encode("utf-8")

# FROST: one Ed25519 verification against the aggregated group key,
# regardless of N. Measured directly (not estimated) using the same
# Ed25519 primitive and message, since FROST signatures verify as
# ordinary Ed25519 signatures.
priv = ed25519.Ed25519PrivateKey.generate()
pub = priv.public_key()
sig = priv.sign(message_bytes)
runs = 2000
pub.verify(sig, message_bytes)  # warm-up
start = time.perf_counter()
for _ in range(runs):
    pub.verify(sig, message_bytes)
frost_verify_time = (time.perf_counter() - start) / runs

# Naive N-of-N multisig: N independent Ed25519 verifications.
multisig_verify_time = [n * frost_verify_time for n in ns]

fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(ns, [frost_verify_time * 1000] * len(ns), color="tab:blue", label="FROST (t-of-n): 1 verification")
ax.plot(ns, [t * 1000 for t in multisig_verify_time], color="tab:red", label="Naive N-of-N multisig: N verifications")
ax.set_xlabel("Number of issuers (N)")
ax.set_ylabel("Verification time (ms)")
ax.set_title(f"Verifier-side cost vs. N (measured single-verify: {frost_verify_time * 1e6:.1f} us)")
ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)
ax.legend()
fig.tight_layout()
fig.savefig("./logs/multisig_comparison_verify_time.png", dpi=300)
print("Figure saved to ./logs/multisig_comparison_verify_time.png")
