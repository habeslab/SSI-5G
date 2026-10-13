#!/usr/bin/env python3
"""
Baseline for the "traditional" single-issuer VC issuance model: one
trusted authority holds a single Ed25519 key and signs the VC directly,
with no threshold signature protocol and no peer-to-peer coordination.

This is the reference point against which the MPC/threshold-signature
scheme (issuer.py, net_issuers.py) is compared, to quantify the overhead
that decentralizing VC issuance across a consortium actually introduces
compared to the conventional single-issuer (SPOF) approach.

The signed payload (base64(JCS-canonicalized VC attributes), encoded as
UTF-8) is built by the same vc_message.build_message_b64() used by the
threshold-signature scripts, and signed the same way the FROST Go nodes
sign it (see main.go: adminStartSignHandler / runSign), so the two
schemes are compared on the exact same message.
"""
import argparse
import base64
import csv
import json
import os
import time

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv

from vc_message import build_message_b64

load_dotenv()

parser = argparse.ArgumentParser(description="Single-issuer VC issuance baseline")
parser.add_argument("--runs", type=int, default=1000,
                     help="Number of repeated sign operations to average over. A single Ed25519 "
                          "signature takes on the order of tens of microseconds, well below "
                          "wall-clock timer resolution/noise, so the reported time is an average "
                          "over many repetitions rather than a single measurement.")
parser.add_argument("--out", type=str, default="./logs/baseline_results.csv",
                     help="CSV file the result is appended to (same n_signers,latency_ms,time "
                          "schema as latency_results.csv, with n_signers=1 and latency_ms=0, so "
                          "it can be overlaid on the same plot as a reference baseline)")
parser.add_argument("--issuer_output", type=str, default="./issuer_output_baseline.json")
args = parser.parse_args()

message_b64 = build_message_b64()
message_bytes = message_b64.encode("utf-8")

private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Warm-up call: the very first invocation pays for one-off costs (e.g. lazy
# imports inside the crypto backend) that would otherwise bias the average.
private_key.sign(message_bytes)

start = time.perf_counter()
for _ in range(args.runs):
    signature = private_key.sign(message_bytes)
end = time.perf_counter()
avg_elapsed = (end - start) / args.runs

print(f"Average single-issuer signing time over {args.runs} runs: {avg_elapsed * 1000:.4f} ms")

os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
file_exists = os.path.isfile(args.out)
with open(args.out, mode="a", newline="") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["n_signers", "latency_ms", "time"])
    writer.writerow([1, 0.0, avg_elapsed])

public_key_b64 = base64.b64encode(
    public_key.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
).decode("utf-8")

output = {
    "sign_issuer_pubkey": public_key_b64,
    "verifiable_cred": {
        "attr": message_b64,
        "issuer_sig": base64.b64encode(signature).decode("utf-8"),
    }
}
with open(args.issuer_output, "w") as f:
    json.dump(output, f, indent=4)
print(f"Baseline issuer output written to {args.issuer_output}")
