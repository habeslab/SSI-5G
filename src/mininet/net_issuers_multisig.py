#!/usr/bin/env python3
"""
Mininet topology and experiment driver for the naive N-of-N multi-
signature baseline (see ../tss/multisig/main.go), used as a second point
of comparison against the FROST threshold-signature scheme (net_issuers.py)
on identical network conditions: same edge-delay topology, same per-host
latency L, same N values.

Unlike the FROST nodes, multisig nodes need no --peers/--threshold flags
and never contact each other: each one independently holds its own key
and only replies to the ctrl host's single request/response round.
"""
import os
import subprocess
import time

from dotenv import load_dotenv
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink

load_dotenv()

NODE_BINARY = os.path.abspath("../tss/node_multisig")
NODE_SRC_DIR = "./multisig"
MULTISIG_MININET_SCRIPT = os.path.abspath("../tss/multisig_mininet.py")

HOST_PREFIX = "10.0.3."
CTRL_IP = f"{HOST_PREFIX}200"

ISSUER_BASE_PORT = int(os.getenv("ISSUER_BASE_PORT"))
PYTHON_INTERPRETER = os.getenv("SSI_INTERPRETER_PATH", "python3")

N_LIST = [int(x) for x in os.getenv("ISSUER_N_LIST", "5,10,20").split(",")]
LATENCIES_MS = [float(x) for x in os.getenv("ISSUER_LATENCIES_MS", "0,5,20,50,100").split(",")]
RESULTS_CSV = os.path.abspath(os.getenv("MULTISIG_LATENCY_RESULTS_CSV", "../tss/logs/multisig_latency_results.csv"))

LINK_BW_MBPS = 100


def build_node_binary():
    if os.path.exists(NODE_BINARY):
        print(f"Binary '{NODE_BINARY}' already exists")
        return
    print("Building multisig node binary...")
    subprocess.run(["go", "build", "-o", NODE_BINARY, NODE_SRC_DIR], check=True, cwd="../tss")
    print("Build completed.\n")


def create_issuer_net(max_n, latency_ms):
    net = Mininet(switch=OVSSwitch, link=TCLink)
    switch = net.addSwitch("s0", failMode="standalone")

    hosts = {}
    for i in range(1, max_n + 1):
        h = net.addHost(f"n{i}", ip=f"{HOST_PREFIX}{i}/24")
        net.addLink(h, switch, bw=LINK_BW_MBPS, delay=f"{latency_ms}ms")
        hosts[i] = h

    ctrl = net.addHost("ctrl", ip=f"{CTRL_IP}/24")
    net.addLink(ctrl, switch, bw=1000, delay="0ms")

    return net, hosts, ctrl


def start_nodes(hosts, n):
    for i in range(1, n + 1):
        cmd = (f'{NODE_BINARY} --id {i} --base-port {ISSUER_BASE_PORT} '
               f'> ./logs/mininet_multisig_node_{i}.log 2>&1 &')
        hosts[i].cmd(cmd)


def stop_nodes(hosts, n):
    for i in range(1, n + 1):
        hosts[i].cmd(f'pkill -f "{NODE_BINARY} --id {i} "')


def run_experiment():
    os.makedirs("./logs", exist_ok=True)
    build_node_binary()

    max_n = max(N_LIST)

    for latency_ms in LATENCIES_MS:
        print(f"\n=== Latency = {latency_ms}ms ===")
        net, hosts, ctrl = create_issuer_net(max_n, latency_ms)
        try:
            net.start()

            for n in N_LIST:
                print(f"--- N = {n} issuers, latency = {latency_ms}ms ---")
                start_nodes(hosts, n)

                out = ctrl.cmd(
                    f'{PYTHON_INTERPRETER} {MULTISIG_MININET_SCRIPT} '
                    f'--n_signers {n} --latency_ms {latency_ms} '
                    f'--host_prefix {HOST_PREFIX} --out {RESULTS_CSV}'
                )
                print(out)

                stop_nodes(hosts, n)
                time.sleep(1)
        finally:
            net.stop()

    print(f"\nAll runs completed. Results saved to {RESULTS_CSV}")


if __name__ == "__main__":
    run_experiment()
