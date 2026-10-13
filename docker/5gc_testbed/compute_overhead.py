#!/usr/bin/env python3
"""
Computes the protocol-level overhead of the SSI handshake + authorization
step relative to native 5G-AKA registration + PDU session establishment,
using timestamps/elapsed-time values already present in the logs saved
by measure_overhead.sh - not the surrounding docker-run wall-clock time,
which is dominated by container startup and would not be a fair
comparison (native registration is measured via UERANSIM's own log
timestamps, not by timing the `docker compose up` invocation either).
"""
import re
import sys
from datetime import datetime

out_dir = sys.argv[1]

TS_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\]")


def registration_time(path):
    """Returns (start, end) datetimes for the first Initial-Registration
    to PDU-Session-established span found in a UERANSIM UE log."""
    start = end = None
    with open(path) as f:
        for line in f:
            m = TS_RE.search(line)
            if not m:
                continue
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
            if start is None and "Sending Initial Registration" in line:
                start = ts
            elif start is not None and end is None and "PDU Session establishment is successful" in line:
                end = ts
                break
    return start, end


def elapsed_from_log(path, pattern):
    with open(path) as f:
        for line in f:
            m = re.search(pattern, line)
            if m:
                return float(m.group(1))
    return None


cold_start, cold_end = registration_time(f"{out_dir}/nr_ue_cold.log")
t_native_cold = (cold_end - cold_start).total_seconds() if cold_start and cold_end else None

warm_start, warm_end = registration_time(f"{out_dir}/nr_ue_warm.log")
t_native_warm = (warm_end - warm_start).total_seconds() if warm_start and warm_end else None

t_ssi = elapsed_from_log(f"{out_dir}/user_overhead0.log", r"Elapsed time: ([0-9.eE+-]+)\.")
t_authz = elapsed_from_log(f"{out_dir}/verifier_ssi.log", r"Elapsed time for authorization: ([0-9.eE+-]+)")

print(f"Native 5G registration+PDU (protocol-only, cold): {t_native_cold*1000:.0f} ms" if t_native_cold else "Native cold: n/a")
print(f"Native 5G registration+PDU (protocol-only, warm): {t_native_warm*1000:.0f} ms" if t_native_warm else "Native warm: n/a")

if t_ssi is not None:
    print(f"SSI handshake (UE<->verifier, protocol-only): {t_ssi*1000:.1f} ms")
if t_authz is not None:
    print(f"Authorization (verifier<->authz, protocol-only): {t_authz*1000:.1f} ms")

if t_ssi is not None and t_authz is not None:
    t_ssi_total = t_ssi + t_authz
    print(f"SSI + authorization total (protocol-only): {t_ssi_total*1000:.1f} ms")

    for label, t_native in [("cold", t_native_cold), ("warm", t_native_warm)]:
        if t_native:
            pct = t_ssi_total / t_native * 100
            print(f"Overhead vs. native ({label}): {pct:.1f}% "
                  f"(combined total if run sequentially after registration: {(t_native + t_ssi_total)*1000:.0f} ms)")

# --- Signaling volume -------------------------------------------------
# The verifier/authz pcap captures are unreliable (tcpdump attached via
# --network container:X sometimes misses the brief exchange), so the
# SSI-side byte count instead comes from the application-level counter
# already used throughout this project (communication.Socket, the same
# one used by the other latency experiments) rather than a second,
# flakier measurement technique. The native side uses the real AMF pcap
# (SCTP/NGAP), so the two numbers are not on an identical basis (wire
# bytes incl. SCTP/IP framing vs. JSON application payload) - reported
# side by side for context, not as a strict apples-to-apples ratio.
import os

vol_kb = elapsed_from_log(f"{out_dir}/user_overhead0.log", r"Communication volume: ([0-9.eE+-]+) KBs")
amf_pcap = f"{out_dir}/amf_registration.pcap"
if vol_kb is not None:
    print(f"SSI application-level payload (UE<->verifier, from application-level byte counter): {vol_kb*1024:.0f} bytes")
if os.path.isfile(amf_pcap):
    print(f"Native NGAP/NAS registration procedure (AMF pcap, SCTP:38412, wire bytes): {os.path.getsize(amf_pcap)} bytes")
