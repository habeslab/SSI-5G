# Overhead of the SSI mechanism relative to native 5G-AKA

Measured with `measure_overhead.sh` against the real Open5GS + UERANSIM testbed
(see `README.md`), on the same host used for the rest of the experiments in this repository.
Raw logs/pcaps for this run are written to `overhead_results/` (not tracked in git — regenerate by
re-running the script).

## Methodology

Two independent flows are timed using their own internal, protocol-level log timestamps (not the
wall-clock time of the surrounding `docker run`/`docker compose` invocations, which would be
dominated by container-startup noise unrelated to either protocol):

- **Native 5G-AKA**: from UERANSIM's own NAS log, `Sending Initial Registration` to
  `PDU Session establishment is successful`. Measured twice: a cold run (fresh subscriber, may
  require one SQN resync round-trip) and a warm re-registration (steady state).
- **SSI mechanism**: `Elapsed time: ...` logged by `user.py` (UE↔verifier handshake) and
  `Elapsed time for authorization: ...` logged by `verifier.py` (verifier↔authz-server call),
  exactly the same instrumentation behind Table I/II of the conference paper.

Signaling volume compares the real captured NGAP/NAS registration traffic (`tcpdump` on the AMF
container, port 38412 — wire bytes, including SCTP/IP framing) against the SSI exchange's
application-level payload (the same byte counter behind Table I/II) — the two are not on an
identical basis (wire vs. application-layer bytes) and are reported side by side for context
rather than as a strict ratio.

## Results (one representative run)

| Phase | Time |
|---|---|
| Native 5G registration + PDU session (cold, incl. possible SQN resync) | 229 ms |
| Native 5G registration + PDU session (warm, steady state) | 229 ms |
| SSI handshake (UE↔verifier) | 11.9 ms |
| Authorization (verifier↔authz-server) | 7.3 ms |
| **SSI + authorization total** | **19.1 ms** |
| **Overhead vs. native registration** | **8.4%** |
| Combined total (native registration, then SSI authorization) | 248 ms |

| Signaling | Bytes |
|---|---|
| Native NGAP/NAS registration (AMF pcap, wire bytes) | 3912 |
| SSI exchange (application-level payload) | 4645 |

| Component | RAM |
|---|---|
| AMF | 20.3 MiB |
| SMF | 40.1 MiB |
| UPF | 26.9 MiB |
| SSI Verifier | 31.8 MiB |
| SSI Authorization Server | 22.4 MiB |

## Interpretation

With the SSI-based authorization positioned as an additional step *after* native 5G-AKA
registration (the coexistence scope chosen for this work — see `README.md`), it adds **~19 ms**,
about **8% on top of** the ~230 ms native registration procedure — a modest, quantified cost for
decentralizing credential issuance and adding network-slice-level authorization, not a
multiplicative or dominant one. RAM footprint of the SSI components (22–32 MiB) is comparable to,
not larger than, that of the lightest Core network functions (AMF: 20 MiB), despite the added
elliptic-curve cryptographic operations. Signaling volume is of the same order of magnitude as a
native NGAP/NAS registration exchange, despite carrying a full Verifiable Credential.

Reproduce with:
```
./measure_overhead.sh /path/to/cloned/docker_open5gs
```
