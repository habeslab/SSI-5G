#!/usr/bin/env python3
"""
One-off diagnostic run reusing net_issuers.py's topology helpers to collect
the per-phase timing breakdown (keygen_wait, signing_dispatch, signing_wait,
status_fetch) written by the instrumented issuer_mininet.py, for a reduced
grid of (N, L) pairs -- this is NOT meant to replace the main latency sweep
behind Table "tab:latency"/Fig. "fig:latency", only to diagnose where the
observed per-issuer linear cost in execution time actually comes from.
"""
import os
import time

import net_issuers as base

N_LIST = [5, 10, 20, 30]
LATENCIES_MS = [0.0, 50.0, 100.0]

RESULTS_CSV = os.path.abspath("../tss/logs/latency_results_breakdown_run.csv")
BREAKDOWN_CSV = os.path.abspath("../tss/logs/latency_breakdown.csv")


def run_experiment():
    os.makedirs("./logs", exist_ok=True)
    base.build_node_binary()

    max_n = max(N_LIST)

    for latency_ms in LATENCIES_MS:
        print(f"\n=== Latency = {latency_ms}ms ===")
        net, hosts, ctrl = base.create_issuer_net(max_n, latency_ms)
        try:
            net.start()

            for n in N_LIST:
                threshold = n - 1
                print(f"--- N = {n} issuers, latency = {latency_ms}ms ---")
                base.start_nodes(hosts, n, threshold)

                out = ctrl.cmd(
                    f'{base.PYTHON_INTERPRETER} {base.ISSUER_MININET_SCRIPT} '
                    f'--n_signers {n} --latency_ms {latency_ms} '
                    f'--host_prefix {base.HOST_PREFIX} --out {RESULTS_CSV} '
                    f'--breakdown_out {BREAKDOWN_CSV}'
                )
                print(out)

                base.stop_nodes(hosts, n)
                time.sleep(1)
        finally:
            net.stop()

    print(f"\nAll runs completed. Breakdown saved to {BREAKDOWN_CSV}")


if __name__ == "__main__":
    run_experiment()
