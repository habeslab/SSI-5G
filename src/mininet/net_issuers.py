#!/usr/bin/env python3
"""
Mininet topology and experiment driver for the threshold-signature (TSS)
issuer consortium, used to measure how VC issuance time scales with both
the number of issuers N and the network latency between them.

Each issuer is modeled as an independent network namespace ("edge-delay"
model): every issuer host is attached to a single shared switch through a
TCLink configured with latency L, so the round-trip time between any two
issuers is 2*L. This mirrors the real-world scenario in which issuers are
distinct administrative entities (e.g. cloud resource managers of
different MNOs) reachable only over a WAN, and reuses the same
methodology already applied to the fronthaul/backhaul links in net.py.

A dedicated, near-zero-latency "ctrl" host triggers keygen/status polling
and the signing request, so that the measured elapsed time reflects the
node-to-node protocol rounds (crossing the emulated L-latency links)
rather than the orchestrator's own access latency.

For each configured latency L, the topology is rebuilt and, for each N in
the configured issuer-count list, the Go node binary is (re)started on N
freshly namespaced hosts and issuer_mininet.py orchestrates keygen and
signing, appending one (n_signers, latency_ms, time) row to the results
CSV.
"""
import os
import subprocess
import time

from dotenv import load_dotenv
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink

load_dotenv()

NODE_BINARY = os.path.abspath("../tss/node")
NODE_SRC = "./main.go"
ISSUER_MININET_SCRIPT = os.path.abspath("../tss/issuer_mininet.py")

HOST_PREFIX = "10.0.2."
CTRL_IP = f"{HOST_PREFIX}200"

ISSUER_BASE_PORT = int(os.getenv("ISSUER_BASE_PORT"))
PYTHON_INTERPRETER = os.getenv("SSI_INTERPRETER_PATH", "python3")

N_LIST = [int(x) for x in os.getenv("ISSUER_N_LIST", "5,10,20").split(",")]
LATENCIES_MS = [float(x) for x in os.getenv("ISSUER_LATENCIES_MS", "0,5,20,50,100").split(",")]
RESULTS_CSV = os.path.abspath(os.getenv("ISSUER_LATENCY_RESULTS_CSV", "../tss/logs/latency_results.csv"))

LINK_BW_MBPS = 100


def build_node_binary():
    if os.path.exists(NODE_BINARY):
        print(f"Binary '{NODE_BINARY}' already exists")
        return
    print("Building Go node binary...")
    subprocess.run(["go", "build", "-o", NODE_BINARY, NODE_SRC], check=True, cwd="../tss")
    print("Build completed.\n")


def create_issuer_net(max_n, latency_ms):
    net = Mininet(switch=OVSSwitch, link=TCLink)

    # No external OpenFlow controller is used here (unlike net.py, which
    # relies on Ryu): standalone mode makes the switch behave as a plain
    # learning L2 switch, otherwise OVS's default secure mode would drop
    # all traffic without a controller telling it what to do.
    switch = net.addSwitch("s0", failMode="standalone")

    hosts = {}
    for i in range(1, max_n + 1):
        h = net.addHost(f"n{i}", ip=f"{HOST_PREFIX}{i}/24")
        net.addLink(h, switch, bw=LINK_BW_MBPS, delay=f"{latency_ms}ms")
        hosts[i] = h

    ctrl = net.addHost("ctrl", ip=f"{CTRL_IP}/24")
    net.addLink(ctrl, switch, bw=1000, delay="0ms")

    return net, hosts, ctrl


def start_nodes(hosts, n, threshold):
    peers_str = ",".join(f"{i}={HOST_PREFIX}{i}" for i in range(1, n + 1))
    for i in range(1, n + 1):
        cmd = (f'{NODE_BINARY} --id {i} --n {n} --base-port {ISSUER_BASE_PORT} '
               f'--threshold {threshold} --peers "{peers_str}" '
               f'> ./logs/mininet_node_{i}.log 2>&1 &')
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
                threshold = n - 1
                print(f"--- N = {n} issuers, latency = {latency_ms}ms ---")
                start_nodes(hosts, n, threshold)

                out = ctrl.cmd(
                    f'{PYTHON_INTERPRETER} {ISSUER_MININET_SCRIPT} '
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
