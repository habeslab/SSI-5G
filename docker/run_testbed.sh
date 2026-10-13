#!/bin/bash
# Real, non-emulated testbed: every component (issuer consortium,
# Network SSI Verifier, Authorization Server, UE) runs as a separate
# Docker container on a real Docker bridge network (independent kernel
# network namespaces, real veth/bridge/iptables forwarding), instead of
# Mininet's SDN-emulation framework. Used to cross-check that the
# reported timings are not an artifact of network emulation.
#
# Usage: ./docker/run_testbed.sh [N_ISSUERS]
set -euo pipefail

N=${1:-3}
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE=ssi-5g:latest
NET=ssi5g-testbed
PY=/opt/ssi-5g/venv/bin/python3.8

cleanup() {
    echo "*** Tearing down testbed containers"
    docker rm -f verifier authz ue $(seq -f "issuer%g" 1 "$N") >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "*** (Re)creating Docker network $NET"
docker network rm "$NET" >/dev/null 2>&1 || true
docker network create "$NET" >/dev/null

echo "*** Building TSS node binary (into node_testbed, so the git-tracked node binary is left untouched)"
docker run --rm -v "$REPO_ROOT/src/tss:/opt/ssi-5g/src/tss" "$IMAGE" \
    bash -c "cd /opt/ssi-5g/src/tss && go build -o node_testbed ./main.go"

echo "*** Starting $N issuer containers"
PEERS=""
for i in $(seq 1 "$N"); do
    PEERS="${PEERS}${PEERS:+,}${i}=issuer${i}"
done
for i in $(seq 1 "$N"); do
    docker run -d --name "issuer${i}" --network "$NET" \
        -v "$REPO_ROOT/src/tss:/opt/ssi-5g/src/tss" \
        -w /opt/ssi-5g/src/tss \
        "$IMAGE" ./node_testbed --id "$i" --n "$N" --base-port 8000 --threshold $((N - 1)) --peers "$PEERS" \
        >/dev/null
done

echo "*** Orchestrating keygen + threshold signing over the Docker network"
rm -f "$REPO_ROOT/src/tss/issuer_output.json"
docker run --rm --network "$NET" \
    -v "$REPO_ROOT/src/tss:/opt/ssi-5g/src/tss" \
    -w /opt/ssi-5g/src/tss \
    "$IMAGE" "$PY" issuer_docker.py --hosts "$(seq -s, -f "issuer%g" 1 "$N")"

echo "*** Generating SSI/authz input files from the issued VC"
docker run --rm \
    -v "$REPO_ROOT/src/tss:/opt/ssi-5g/src/tss" \
    -v "$REPO_ROOT/src/ssi:/opt/ssi-5g/src/ssi" \
    -w /opt/ssi-5g/src/ssi \
    "$IMAGE" "$PY" init_json.py

echo "*** Starting Authorization Server and Network SSI Verifier containers"
docker run -d --name authz --network "$NET" \
    -v "$REPO_ROOT/src/ssi:/opt/ssi-5g/src/ssi" \
    -w /opt/ssi-5g/src/ssi \
    "$IMAGE" "$PY" authz_server.py --authz_server_ip 0.0.0.0 --authz_server_port 9090 \
        --input_folder /opt/ssi-5g/src/ssi/inputs

docker run -d --name verifier --network "$NET" \
    -v "$REPO_ROOT/src/ssi:/opt/ssi-5g/src/ssi" \
    -w /opt/ssi-5g/src/ssi \
    "$IMAGE" "$PY" verifier.py --verifier_port 7000 --input_folder /opt/ssi-5g/src/ssi/inputs \
        --authz_server_ip authz --authz_server_port 9090

sleep 1

echo "*** Running the UE (one-shot) against the verifier over the Docker network"
docker run --rm --name ue --network "$NET" \
    -v "$REPO_ROOT/src/ssi:/opt/ssi-5g/src/ssi" \
    -w /opt/ssi-5g/src/ssi \
    "$IMAGE" "$PY" user.py --verifier_ip verifier --verifier_port 7000 \
        --input_folder /opt/ssi-5g/src/ssi/inputs --ue_id docker0

echo "*** UE log (authentication result):"
cat "$REPO_ROOT/src/ssi/logs/user_docker0.log"
echo
echo "*** Verifier log (tail):"
tail -20 "$REPO_ROOT/src/ssi/logs/verifier.log"
echo
echo "*** Authz server log (tail):"
tail -10 "$REPO_ROOT/src/ssi/logs/authz_server.log"
