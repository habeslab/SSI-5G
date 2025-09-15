#!/usr/bin/env python3
import subprocess
import time
import base64
import json
import requests
import signal
import os
import jcs

# ===============================
# Configurazione
# ===============================
N = 4
BASE = 8000
TH = 3

NODE_BINARY = "./node"
CMD_PATH = "./main.go"

SIGNERS = list(range(1, TH + 2))  # primi TH+1 nodi

MESSAGE_DICT = {
    "plmnId": "PLMN ID",
    "siteId": "SITE ID",
    "sliceId": "SLICE ID",
    "expirationDate": "EXPIRATION DATE"
}
MESSAGE_JSON = jcs.canonicalize(MESSAGE_DICT)
MESSAGE_B64 = base64.b64encode(MESSAGE_JSON).decode("utf-8")


# ===============================
# 1) Build
# ===============================
if not os.path.exists(NODE_BINARY):
    print("Building Go node binary...")
    subprocess.run(["go", "build", "-o", NODE_BINARY, CMD_PATH], check=True)
    print("Build completed.\n")
else:
    print(f"Binary '{NODE_BINARY}' already exists\n")

# ===============================
# 2) Launch nodes in background
# ===============================
processes = []

for i in range(1, N + 1):
    port = BASE + i - 1
    print(f"Starting node {i} on port {port}")

    proc = subprocess.Popen(
        [NODE_BINARY, "--id", str(i), "--n", str(N), "--base-port", str(BASE), "--threshold", str(TH)],
        stderr=subprocess.STDOUT
    )
    processes.append(proc)
    time.sleep(0.1)

time.sleep(2)

# ===============================
# Helper: wait for keygen
# ===============================
def wait_keygen(base, nodes, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        all_done = True
        for node_id in nodes:
            url = f"http://127.0.0.1:{base + node_id - 1}/status"
            try:
                r = requests.get(url, timeout=2)
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

print("\nWaiting for all signers to finish keygen...")
if not wait_keygen(BASE, SIGNERS, timeout=60):
    print("ERROR: Keygen not completed in time, aborting.")
    for proc in processes:
        proc.kill()
    exit(1)
print("Keygen completed.\n")

# ===============================
# 3) Request signing
# ===============================
print("Requesting signatures from nodes:", SIGNERS)
for node_id in SIGNERS:
    port = BASE + node_id - 1
    url = f"http://127.0.0.1:{port}/admin/start-sign"
    payload = {"signers": SIGNERS, "message": MESSAGE_B64}
    try:
        resp = requests.post(url, json=payload)
        print(f"Node {node_id} response status: {resp.status_code}")
    except requests.RequestException as e:
        print(f"Error contacting node {node_id}: {e}")

# ===============================
# 4) Wait and fetch statuses
# ===============================
time.sleep(3)

for node_id in SIGNERS:
    port = BASE + node_id - 1
    try:
        r = requests.get(f"http://127.0.0.1:{port}/status")
        print(f"\n--- Node {node_id} status ---")
        print(json.dumps(r.json(), indent=4))
    except Exception as e:
        print(f"Error fetching status for node {node_id}: {e}")

print("\nCheck issuer_output.json for the final aggregated result.")

# ===============================
# 5) Cleanup
# ===============================
time.sleep(2)
print("Shutting down all nodes...")
for proc in processes:
    try:
        proc.send_signal(signal.SIGINT)
    except Exception:
        pass
time.sleep(1)
for proc in processes:
    proc.terminate()
