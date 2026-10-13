#!/bin/bash
# Measures the overhead the SSI-based authorization step adds on top of
# native 5G-AKA registration, on three axes:
#   1) latency  - time for native 5G registration+PDU session vs. time
#                 for the SSI handshake + authorization step
#   2) signaling volume - bytes captured for AMF's NGAP registration
#                 procedure (SCTP:38412) vs. bytes for the SSI/DIDComm
#                 exchange and the authz mTLS call
#   3) compute footprint - RAM of the 5G Core NFs (AMF/SMF/UPF) vs. the
#                 SSI verifier/authz-server processes
#
# Captures are taken with tcpdump attached to each container's own
# network namespace (--network container:<name>), using the
# docker_open5gs image (already has tcpdump) so no image needs rebuilding.
#
# Prerequisites: docker_open5gs + docker_ueransim images available (see
# ../5gc_testbed/README.md), and the ssi-5g image built (see repo root
# Dockerfile). Run from this directory.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
O5GS_DIR="${1:?Usage: measure_overhead.sh <path-to-cloned-docker_open5gs-repo>}"
OUT="$HERE/overhead_results"
mkdir -p "$OUT"

echo "*** Preparing docker_open5gs directory with our config"
cp "$HERE/open5gs.env" "$O5GS_DIR/.env"
cp "$HERE/sa-deploy-trimmed.yaml" "$O5GS_DIR/"
sed -i "s/opType: 'OP'/opType: 'OPC'/" "$O5GS_DIR/ueransim/ueransim-ue.yaml"

cleanup() {
    echo "*** Cleaning up"
    (cd "$O5GS_DIR" && docker compose -f nr-ue.yaml --env-file .env down >/dev/null 2>&1 || true)
    (cd "$O5GS_DIR" && docker compose -f nr-gnb.yaml --env-file .env down >/dev/null 2>&1 || true)
    (cd "$O5GS_DIR" && docker compose -f sa-deploy-trimmed.yaml --env-file .env down -v >/dev/null 2>&1 || true)
    docker rm -f ssi-verifier ssi-authz >/dev/null 2>&1 || true
    docker network rm ssi5g-overhead >/dev/null 2>&1 || true
    # go build in phase B writes to the bind-mounted src/tss/node, which is
    # git-tracked (built by the original author, possibly against a
    # different glibc) - restore it so this measurement leaves no diff.
    (cd "$REPO_ROOT" && git checkout -- src/tss/node 2>/dev/null || true)
}
trap cleanup EXIT

# ===========================================================================
# Phase A: native 5G-AKA registration - latency, signaling volume, RAM
# ===========================================================================
echo "*** [A] Bringing up the 5G Core"
(cd "$O5GS_DIR" && docker compose -f sa-deploy-trimmed.yaml --env-file .env up -d)
sleep 8

echo "*** [A] Provisioning test subscriber"
"$HERE/provision_subscriber.sh"

echo "*** [A] Capturing AMF NGAP/SCTP traffic during registration"
# No --rm here: `docker stop` would otherwise remove the container (and
# the pcap living in its own, non-shared filesystem) before we can copy
# it out with `docker cp`.
docker run -d --name amf_capture --network container:amf docker_open5gs \
    tcpdump -i any -w /tmp/amf.pcap port 38412 >/dev/null

echo "*** [A] Bringing up gNB"
(cd "$O5GS_DIR" && docker compose -f nr-gnb.yaml --env-file .env up -d)
sleep 2

echo "*** [A] Bringing up UE (cold start, SQN resync likely on first attempt)"
t_reg_start=$(date +%s.%N)
(cd "$O5GS_DIR" && docker compose -f nr-ue.yaml --env-file .env up -d)

echo "*** [A] Waiting for PDU session establishment..."
ok=0
for i in $(seq 1 90); do
    if docker logs nr_ue 2>&1 | grep -qi "PDU session establishment is successful"; then
        ok=1
        break
    fi
    sleep 1
done
t_reg_end=$(date +%s.%N)
if [ "$ok" -eq 0 ]; then
    echo "WARNING: PDU session not observed within 90s, dumping nr_ue log:"
    docker logs nr_ue 2>&1 | tail -40
fi
docker logs nr_ue > "$OUT/nr_ue_cold.log" 2>&1

docker stop amf_capture >/dev/null 2>&1 || true
docker cp amf_capture:/tmp/amf.pcap "$OUT/amf_registration.pcap" 2>/dev/null || true
docker rm -f amf_capture >/dev/null 2>&1 || true

t_native_cold_wall=$(echo "$t_reg_end - $t_reg_start" | bc)
echo "Native 5G registration+PDU (cold, wall time incl. container startup): ${t_native_cold_wall}s" | tee "$OUT/summary.txt"

echo "*** [A] Re-registering UE (warm, steady-state, no resync expected)"
(cd "$O5GS_DIR" && docker compose -f nr-ue.yaml --env-file .env restart)
t_warm_start=$(date +%s.%N)
warm_ok=0
for i in $(seq 1 90); do
    n=$(docker logs nr_ue 2>&1 | grep -ci "PDU session establishment is successful")
    if [ "$n" -ge 2 ]; then warm_ok=1; break; fi
    sleep 1
done
t_warm_end=$(date +%s.%N)
if [ "$warm_ok" -eq 0 ]; then
    echo "WARNING: warm PDU session not observed within 90s, dumping nr_ue log:"
    docker logs nr_ue 2>&1 | tail -40
fi
docker logs nr_ue > "$OUT/nr_ue_warm.log" 2>&1
t_native_warm_wall=$(echo "$t_warm_end - $t_warm_start" | bc)
echo "Native 5G re-registration+PDU (warm, wall time incl. container restart): ${t_native_warm_wall}s" | tee -a "$OUT/summary.txt"

echo "*** [A] RAM footprint of Core NFs"
docker stats --no-stream --format "{{.Name}}: {{.MemUsage}}" amf smf upf | tee -a "$OUT/summary.txt"

# ===========================================================================
# Phase B: SSI handshake + authorization - latency, signaling volume, RAM
# ===========================================================================
echo "*** [B] Building TSS/SSI images if needed and starting verifier+authz"
docker network create ssi5g-overhead >/dev/null 2>&1 || true

# issuer.py hardcodes "./node" as the binary it builds-if-missing and
# runs; force a fresh build there (glibc-matched to this container) since
# the bind-mounted host copy is a git-tracked binary that may have been
# built against a different glibc (restored via git checkout in cleanup).
rm -f "$REPO_ROOT/src/tss/node"
docker run --rm -v "$REPO_ROOT/src/tss:/opt/ssi-5g/src/tss" ssi-5g:latest \
    bash -c "cd /opt/ssi-5g/src/tss && /opt/ssi-5g/venv/bin/python3.8 issuer.py --n_signers 3" \
    > "$OUT/issuer.log" 2>&1
# Simplest, most portable path: reuse the already-validated single-host
# issuer.py flow (N=3, localhost) purely to produce a fresh issuer_output.json;
# the Docker-network variant (issuer_docker.py) is unnecessary here since
# only the resulting VC matters for this measurement.

docker run --rm \
    -v "$REPO_ROOT/src/tss:/opt/ssi-5g/src/tss" \
    -v "$REPO_ROOT/src/ssi:/opt/ssi-5g/src/ssi" \
    -w /opt/ssi-5g/src/ssi \
    ssi-5g:latest /opt/ssi-5g/venv/bin/python3.8 init_json.py

docker run -d --name ssi-authz --network ssi5g-overhead \
    -v "$REPO_ROOT/src/ssi:/opt/ssi-5g/src/ssi" -w /opt/ssi-5g/src/ssi \
    ssi-5g:latest /opt/ssi-5g/venv/bin/python3.8 authz_server.py \
        --authz_server_ip 0.0.0.0 --authz_server_port 9090 --input_folder /opt/ssi-5g/src/ssi/inputs

docker run -d --name ssi-verifier --network ssi5g-overhead \
    -v "$REPO_ROOT/src/ssi:/opt/ssi-5g/src/ssi" -w /opt/ssi-5g/src/ssi \
    ssi-5g:latest /opt/ssi-5g/venv/bin/python3.8 verifier.py \
        --verifier_port 7000 --input_folder /opt/ssi-5g/src/ssi/inputs \
        --authz_server_ip ssi-authz --authz_server_port 9090
sleep 1

echo "*** [B] Capturing verifier+authz traffic during the SSI handshake"
docker run -d --name verifier_capture --network container:ssi-verifier docker_open5gs \
    tcpdump -i any -w /tmp/verifier.pcap "port 7000 or port 9090" >/dev/null
docker run -d --name authz_capture --network container:ssi-authz docker_open5gs \
    tcpdump -i any -w /tmp/authz.pcap port 9090 >/dev/null
sleep 1

t_ssi_start=$(date +%s.%N)
docker run --rm --network ssi5g-overhead \
    -v "$REPO_ROOT/src/ssi:/opt/ssi-5g/src/ssi" -w /opt/ssi-5g/src/ssi \
    ssi-5g:latest /opt/ssi-5g/venv/bin/python3.8 user.py \
        --verifier_ip ssi-verifier --verifier_port 7000 \
        --input_folder /opt/ssi-5g/src/ssi/inputs --ue_id overhead0
t_ssi_end=$(date +%s.%N)
t_ssi_wall=$(echo "$t_ssi_end - $t_ssi_start" | bc)

docker stop verifier_capture authz_capture >/dev/null 2>&1 || true
docker cp verifier_capture:/tmp/verifier.pcap "$OUT/verifier_ssi.pcap" 2>/dev/null || true
docker cp authz_capture:/tmp/authz.pcap "$OUT/authz_ssi.pcap" 2>/dev/null || true
docker rm -f verifier_capture authz_capture >/dev/null 2>&1 || true

cp "$REPO_ROOT/src/ssi/logs/user_overhead0.log" "$OUT/" 2>/dev/null || true
cp "$REPO_ROOT/src/ssi/logs/verifier.log" "$OUT/verifier_ssi.log" 2>/dev/null || true
cp "$REPO_ROOT/src/ssi/logs/authz_server.log" "$OUT/authz_ssi.log" 2>/dev/null || true

echo "SSI handshake + authorization (docker-run wall time, incl. container startup): ${t_ssi_wall}s" | tee -a "$OUT/summary.txt"
echo "*** [B] RAM footprint of SSI components"
docker stats --no-stream --format "{{.Name}}: {{.MemUsage}}" ssi-verifier ssi-authz | tee -a "$OUT/summary.txt"

# ===========================================================================
# Report
# ===========================================================================
echo "*** Signaling volume (pcap bytes)"
for f in amf_registration verifier_ssi authz_ssi; do
    if [ -f "$OUT/$f.pcap" ]; then
        size=$(stat -c%s "$OUT/$f.pcap")
        echo "$f.pcap: ${size} bytes" | tee -a "$OUT/summary.txt"
    fi
done

echo
echo "*** Protocol-level overhead (excludes container/orchestration startup noise on both sides):"
python3 "$HERE/compute_overhead.py" "$OUT" | tee -a "$OUT/summary.txt"

echo
echo "All artifacts saved under $OUT"
