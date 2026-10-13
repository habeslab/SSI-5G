#!/usr/bin/env python3
"""
One-off diagnostic: re-measure N=30, L=20ms three times to check whether
the Table V cell at this (N, L) pair (originally 12.265s, out of line with
the otherwise clean linear trend at L=5/50/100) is measurement noise or a
reproducible effect.
"""
import os
import time

import net_issuers as base

N = 30
LATENCY_MS = 20.0
REPEATS = 3

RESULTS_CSV = os.path.abspath("../tss/logs/latency_results_outlier_check.csv")


def run_experiment():
    os.makedirs("./logs", exist_ok=True)
    base.build_node_binary()

    net, hosts, ctrl = base.create_issuer_net(N, LATENCY_MS)
    try:
        net.start()

        for repeat in range(1, REPEATS + 1):
            threshold = N - 1
            print(f"--- Repeat {repeat}/{REPEATS}: N={N}, L={LATENCY_MS}ms ---")
            base.start_nodes(hosts, N, threshold)

            out = ctrl.cmd(
                f'{base.PYTHON_INTERPRETER} {base.ISSUER_MININET_SCRIPT} '
                f'--n_signers {N} --latency_ms {LATENCY_MS} '
                f'--host_prefix {base.HOST_PREFIX} --out {RESULTS_CSV}'
            )
            print(out)

            base.stop_nodes(hosts, N)
            time.sleep(1)
    finally:
        net.stop()

    print(f"\nAll repeats completed. Results saved to {RESULTS_CSV}")


if __name__ == "__main__":
    run_experiment()
