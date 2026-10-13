#!/bin/bash
# Provisions the UERANSIM test UE (IMSI/K/OPC from open5gs.env) as a
# subscriber in the running Open5GS MongoDB, using open5gs-dbctl instead
# of the WebUI (which this trimmed deployment does not include).
set -euo pipefail

ENV_FILE="$(dirname "${BASH_SOURCE[0]}")/open5gs.env"
IMSI=$(grep '^UE1_IMSI=' "$ENV_FILE" | cut -d= -f2)
KI=$(grep '^UE1_KI=' "$ENV_FILE" | cut -d= -f2)
OPC=$(grep '^UE1_OP=' "$ENV_FILE" | cut -d= -f2)
MONGO_IP=$(grep '^MONGO_IP=' "$ENV_FILE" | cut -d= -f2)

docker run --rm --network docker_open5gs_default docker_open5gs \
    /open5gs/misc/db/open5gs-dbctl --db_uri="mongodb://${MONGO_IP}/open5gs" add "$IMSI" "$KI" "$OPC"

echo "Subscriber $IMSI provisioned."
