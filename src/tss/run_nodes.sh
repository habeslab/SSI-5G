#!/usr/bin/env bash
set -e

N=10
BASE=8000
TH=7

# 1) build
go build -o node ./cmd/node

# 2) launch nodes in background (logs go to node_<id>.log)
for i in $(seq 1 $N); do
  echo "starting node $i on port $((BASE + i - 1))"
  ./node --id $i --n $N --base-port $BASE --threshold $TH > node_${i}.log 2>&1 &
  sleep 0.1
done

sleep 2

# 3) pick signers (first TH+1 nodes for demo) and request them to sign
SIGNERS="$(seq -s, 1 $((TH+1)))"
MESSAGE="ciao mario"
for id in $(echo $SIGNERS | tr ',' ' '); do
  curl -s -X POST "http://127.0.0.1:$((BASE + id - 1))/admin/start-sign" -H "Content-Type: application/json" -d "{\"signers\":[${SIGNERS}],\"message\":\"${MESSAGE}\"}"
done

# 4) wait and fetch statuses
sleep 3
for id in $(echo $SIGNERS | tr ',' ' '); do
  echo "--- status node $id ---"
  curl -s "http://127.0.0.1:$((BASE + id - 1))/status" | jq .
done

echo "Logs per nodo: node_*.log"
