#!/usr/bin/env python3
"""
Orchestrator for the VC issuance experiment when issuer nodes run as
separate Docker containers on a real Docker bridge network (see
docker/run_testbed.sh), addressed by container/service name rather than
by a Mininet-assigned IP prefix (see issuer_mininet.py) or all on
127.0.0.1 (see issuer.py).

Communication between containers here crosses the actual Linux kernel
networking stack (veth pair + bridge + iptables, real TCP/IP), not an
SDN-emulation framework, which is the point of this variant: it lets the
timing/volume results be cross-checked against the Mininet-based ones on
a deployment technology that could genuinely be used in production
(containerized Cloud RAN network functions), rather than relying solely
on a research network emulator.
"""
import time
import json
import requests
import os
import argparse
from dotenv import load_dotenv

from vc_message import build_message_b64

load_dotenv()

parser = argparse.ArgumentParser(description="Orchestrator for VC issuance over a Docker-network issuer topology")
parser.add_argument("--hosts", type=str, required=True,
                     help="Comma-separated container hostnames, in issuer-id order (id 1 first)")
parser.add_argument("--base_port", type=int, default=int(os.getenv("ISSUER_BASE_PORT", "8000")))
args = parser.parse_args()

HOSTS = args.hosts.split(",")
N = len(HOSTS)
SIGNERS = list(range(1, N + 1))

MESSAGE_B64 = build_message_b64()


def node_url(node_id, path):
    host = HOSTS[node_id - 1]
    return f"http://{host}:{args.base_port + node_id - 1}{path}"


def wait_keygen(timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if all(requests.get(node_url(i, "/status"), timeout=2).json().get("keygen_done", False)
               for i in SIGNERS):
            return True
        time.sleep(0.5)
    return False


def wait_sign(timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if all(requests.get(node_url(i, "/status"), timeout=2).json().get("signature_base64")
               for i in SIGNERS):
            return True
        time.sleep(0.2)
    return False


print(f"Waiting for keygen on {N} issuer containers ({HOSTS})...")
if not wait_keygen():
    raise SystemExit("ERROR: keygen not completed in time")
print("Keygen completed.")

start = time.perf_counter()
for node_id in SIGNERS:
    payload = {"signers": SIGNERS, "message": MESSAGE_B64}
    resp = requests.post(node_url(node_id, "/admin/start-sign"), json=payload)
    print(f"Node {node_id} response status: {resp.status_code}")

if not wait_sign():
    raise SystemExit("ERROR: signing not completed in time")
elapsed = time.perf_counter() - start

for node_id in SIGNERS:
    status = requests.get(node_url(node_id, "/status")).json()
    print(f"--- Node {node_id} status ---")
    print(json.dumps(status, indent=4))

print(f"\nSigning completed in {elapsed:.3f}s across {N} Docker-networked issuers.")
print("Check issuer_output.json for the final aggregated result.")
