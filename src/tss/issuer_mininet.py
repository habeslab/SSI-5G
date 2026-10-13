#!/usr/bin/env python3
"""
Orchestrator for the VC issuance experiment when issuer nodes run on
separate Mininet hosts (one namespace per issuer, connected through
TCLinks with a configurable per-host latency).

Unlike issuer.py, this script does NOT build the Go binary nor spawn the
node processes: that is done by net_issuers.py, once per host, so that
each node's traffic actually crosses an emulated network link with the
latency under test. This script only orchestrates keygen-completion
polling and the signing request/collection phase, and appends the
measured elapsed time to a CSV file also tagged with the link latency,
so that execution time can be studied as a function of both N and
inter-issuer latency.

Per-phase timing breakdown: in addition to the total elapsed time (kept
for backward compatibility with latency_results.csv), this script also
times four sub-phases separately -- keygen_wait (sequential /status
polling until all issuers report keygen_done), signing_dispatch (the
sequential loop of /admin/start-sign POSTs, one per issuer), signing_wait
(sequential /status polling until all issuers report a signature) and
status_fetch (final informational /status round) -- and appends them to
a separate breakdown CSV, so that the N-dependent cost identified in
Section "Impact of Inter-Issuer Network Latency" can be attributed to a
specific phase instead of being guessed at.
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

parser = argparse.ArgumentParser(description="Orchestrator for VC issuance over a Mininet issuer topology")
parser.add_argument("--n_signers", type=int, required=True, help="Num of signers")
parser.add_argument("--latency_ms", type=float, required=True,
                     help="Per-host link latency (ms) configured on the Mininet topology, only used for logging")
parser.add_argument("--host_prefix", type=str, default="10.0.2.",
                     help="IP prefix used for issuer hosts (host i has IP <prefix><i>)")
parser.add_argument("--out", type=str, default="./logs/latency_results.csv",
                     help="Path of the CSV file where results are appended")
parser.add_argument("--breakdown_out", type=str, default="./logs/latency_breakdown.csv",
                     help="Path of the CSV file where per-phase timing breakdown is appended")
args = parser.parse_args()

N = args.n_signers
BASE = int(os.getenv("ISSUER_BASE_PORT"))
TH = N - 1
SIGNERS = list(range(1, TH + 2))  # primi TH+1 nodi, come in issuer.py

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


def save_breakdown_csv(n_signers, latency_ms, keygen_wait_s, signing_dispatch_s, signing_wait_s, status_fetch_s, total_s):
    file_exists = os.path.isfile(args.breakdown_out)
    os.makedirs(os.path.dirname(args.breakdown_out), exist_ok=True)

    with open(args.breakdown_out, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["n_signers", "latency_ms", "keygen_wait_s", "signing_dispatch_s",
                              "signing_wait_s", "status_fetch_s", "total_s"])
        writer.writerow([n_signers, latency_ms, keygen_wait_s, signing_dispatch_s,
                          signing_wait_s, status_fetch_s, total_s])


def wait_keygen(nodes, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        all_done = True
        for node_id in nodes:
            try:
                r = requests.get(node_url(node_id, "/status"), timeout=2)
                st = r.json()
                if not st.get("keygen_done", False):
                    all_done = False
                    break
            except Exception:
                all_done = False
                break
        if all_done:
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


# ===============================
# Begin time measurement
# ===============================
t0 = time.perf_counter()

print("\nWaiting for all signers to finish keygen...")
if not wait_keygen(SIGNERS, timeout=240):
    print("ERROR: Keygen not completed in time, aborting.")
    exit(1)
print("Keygen completed.\n")

t1 = time.perf_counter()  # end of keygen_wait phase

print("Requesting signatures from nodes:", SIGNERS)
for node_id in SIGNERS:
    payload = {"signers": SIGNERS, "message": MESSAGE_B64}
    try:
        resp = requests.post(node_url(node_id, "/admin/start-sign"), json=payload)
        print(f"Node {node_id} response status: {resp.status_code}")
    except requests.RequestException as e:
        print(f"Error contacting node {node_id}: {e}")

t2 = time.perf_counter()  # end of signing_dispatch phase (sequential POST loop)

if not wait_sign(SIGNERS, timeout=240):
    print("ERROR: Signing not completed in time, aborting.")
    exit(1)

t3 = time.perf_counter()  # end of signing_wait phase

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
t4 = time.perf_counter()

elapsed = t4 - t0
keygen_wait_s = t1 - t0
signing_dispatch_s = t2 - t1
signing_wait_s = t3 - t2
status_fetch_s = t4 - t3

print(f"\nElapsed time for N={N}, latency={args.latency_ms}ms: {elapsed:.3f}s")
print(f"  keygen_wait={keygen_wait_s:.3f}s  signing_dispatch={signing_dispatch_s:.3f}s  "
      f"signing_wait={signing_wait_s:.3f}s  status_fetch={status_fetch_s:.3f}s")

save_result_csv(N, args.latency_ms, elapsed)
save_breakdown_csv(N, args.latency_ms, keygen_wait_s, signing_dispatch_s, signing_wait_s, status_fetch_s, elapsed)
