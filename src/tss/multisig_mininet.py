#!/usr/bin/env python3
"""
Orchestrator for the naive N-of-N multi-signature baseline (see
./multisig/main.go), run on separate Mininet hosts exactly like
issuer_mininet.py, so the two schemes are compared under identical
network conditions (same topology, same per-host latency L).

Unlike issuer_mininet.py, there is no key-generation phase to poll for:
each node already holds its own independent key as soon as it starts, so
the measured elapsed time only covers the single request/response round
needed to collect N independent signatures.
"""
import time
import json
import requests
import os
import csv
import argparse
from dotenv import load_dotenv
from vc_message import build_message_b64

load_dotenv()

parser = argparse.ArgumentParser(description="Orchestrator for the N-of-N multisig baseline over a Mininet topology")
parser.add_argument("--n_signers", type=int, required=True, help="Num of signers")
parser.add_argument("--latency_ms", type=float, required=True,
                     help="Per-host link latency (ms) configured on the Mininet topology, only used for logging")
parser.add_argument("--host_prefix", type=str, default="10.0.3.",
                     help="IP prefix used for issuer hosts (host i has IP <prefix><i>)")
parser.add_argument("--out", type=str, default="./logs/multisig_latency_results.csv",
                     help="Path of the CSV file where results are appended")
args = parser.parse_args()

N = args.n_signers
BASE = int(os.getenv("ISSUER_BASE_PORT"))
SIGNERS = list(range(1, N + 1))

MESSAGE_B64 = build_message_b64()


def node_url(node_id, path):
    return f"http://{args.host_prefix}{node_id}:{BASE + node_id - 1}{path}"


def save_result_csv(n_signers, latency_ms, time_value):
    file_exists = os.path.isfile(args.out)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    with open(args.out, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["n_signers", "latency_ms", "time"])
        writer.writerow([n_signers, latency_ms, time_value])


def wait_ready(nodes, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        all_up = True
        for node_id in nodes:
            try:
                requests.get(node_url(node_id, "/status"), timeout=2)
            except Exception:
                all_up = False
                break
        if all_up:
            return True
        time.sleep(0.5)
    return False


def wait_sign(nodes, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        all_done = True
        for node_id in nodes:
            try:
                r = requests.get(node_url(node_id, "/status"), timeout=2)
                st = r.json()
                if not st.get("signature_base64"):
                    all_done = False
                    break
            except Exception:
                all_done = False
                break
        if all_done:
            return True
        time.sleep(0.2)
    return False


print("\nWaiting for all nodes to be reachable...")
if not wait_ready(SIGNERS, timeout=60):
    print("ERROR: nodes not reachable in time, aborting.")
    exit(1)

# ===============================
# Begin time measurement
# ===============================
start = time.perf_counter()

print("Requesting independent signatures from nodes:", SIGNERS)
for node_id in SIGNERS:
    payload = {"message": MESSAGE_B64}
    try:
        resp = requests.post(node_url(node_id, "/admin/start-sign"), json=payload)
        print(f"Node {node_id} response status: {resp.status_code}")
    except requests.RequestException as e:
        print(f"Error contacting node {node_id}: {e}")

if not wait_sign(SIGNERS, timeout=240):
    print("ERROR: Signing not completed in time, aborting.")
    exit(1)

for node_id in SIGNERS:
    try:
        r = requests.get(node_url(node_id, "/status"))
        print(f"\n--- Node {node_id} status ---")
        print(json.dumps(r.json(), indent=4))
    except Exception as e:
        print(f"Error fetching status for node {node_id}: {e}")

# ===============================
# End time measurement
# ===============================
end = time.perf_counter()
elapsed = end - start

print(f"\nElapsed time for N={N}, latency={args.latency_ms}ms: {elapsed:.3f}s")
save_result_csv(N, args.latency_ms, elapsed)
