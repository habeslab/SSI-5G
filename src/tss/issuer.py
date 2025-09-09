#!/usr/bin/env python3
import subprocess
import time
import base64
import json
import requests
from pathlib import Path
import signal
import os
import jcs

# ===============================
# Configurazione
# ===============================
N = 6
BASE = 8000
TH = 3

NODE_BINARY = "./node"
CMD_PATH = "./main.go"

SIGNERS = list(range(1, TH + 2))  # primi TH+1 nodi

MESSAGE_DICT = {"name": "francesco", "age": 24}
MESSAGE_JSON = jcs.canonicalize(MESSAGE_DICT)
MESSAGE_B64 = base64.b64encode(jcs.canonicalize(MESSAGE_DICT)).decode("utf-8")


# ===============================
# 1) Build
# ===============================
if not os.path.exists(NODE_BINARY):
    print("Building Go node binary...")
    subprocess.run(["go", "build", "-o", NODE_BINARY, CMD_PATH], check=True)
    print("Build completed.\n")
else:
    print(f"Bianry '{NODE_BINARY}' already exists\n")

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
# 3) Request signing
# ===============================
print("\nRequesting signatures from nodes:", SIGNERS)
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
    url = f"http://127.0.0.1:{port}/status"
    print(f"\n--- status node {node_id} ---")
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))
    except requests.RequestException as e:
        print(f"Error fetching status from node {node_id}: {e}")
    except json.JSONDecodeError:
        print(f"Invalid JSON received from node {node_id}: {resp.text}")

print("\nLogs per nodo: node_*.log")

# ===============================
# 5) Cleanup: terminare tutti i processi
# ===============================
print("\nTerminating all node processes...")
for proc in processes:
    try:
        proc.send_signal(signal.SIGINT)  # invia CTRL+C al processo
        proc.wait(timeout=5)             # aspetta che termini
    except subprocess.TimeoutExpired:
        proc.kill()                      # se non risponde, forza kill
        proc.wait()
print("All node processes terminated.")
