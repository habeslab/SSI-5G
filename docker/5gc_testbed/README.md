# 5G SA Core + RAN testbed (Open5GS + UERANSIM)

This is a standards-compliant, 3GPP-conformant 5G Standalone (SA) Core network and
gNB/UE simulator, used to validate the C-RAN/authentication work in this repository against a
**real 5G stack** rather than only Mininet's SDN emulation or generic containers.

It relies on two established open-source projects (not vendored into this repo — clone them
separately):

- [`herlesupreeth/docker_open5gs`](https://github.com/herlesupreeth/docker_open5gs) — Dockerized
  Open5GS 5G Core (NRF, SCP, AUSF, UDM, UDR, PCF, BSF, NSSF, SMF, UPF, AMF) and UERANSIM images.
- [`aligungr/UERANSIM`](https://github.com/aligungr/UERANSIM) — the UERANSIM gNB/UE simulator
  itself (pulled as a pre-built image by the compose files above, so cloning it is only needed if
  you want to inspect/rebuild it).

The files in this directory (`open5gs.env`, `sa-deploy-trimmed.yaml`, `provision_subscriber.sh`)
are **our** configuration on top of that upstream project: a trimmed compose file (core NFs only,
no WebUI/Grafana/metrics, which aren't needed to validate registration) and network/subscriber
settings adjusted to avoid conflicting with other Docker networks on the host.

## Reproducing

```bash
git clone https://github.com/herlesupreeth/docker_open5gs.git
cd docker_open5gs

# Pull pre-built images instead of building from source
docker pull ghcr.io/herlesupreeth/docker_open5gs:master && docker tag ghcr.io/herlesupreeth/docker_open5gs:master docker_open5gs
docker pull ghcr.io/herlesupreeth/docker_ueransim:master && docker tag ghcr.io/herlesupreeth/docker_ueransim:master docker_ueransim

# Use our configuration (adjust TEST_NETWORK in open5gs.env first if 172.30.0.0/24 conflicts with
# an existing Docker network on your host: `docker network inspect $(docker network ls -q)`)
cp /path/to/SSI-5G/docker/5gc_testbed/open5gs.env .env
cp /path/to/SSI-5G/docker/5gc_testbed/sa-deploy-trimmed.yaml .
sed -i "s/opType: 'OP'/opType: 'OPC'/" ueransim/ueransim-ue.yaml   # UE1_OP in .env is an OPC value, not OP

# Bring up the core, then provision the test UE as a subscriber
docker compose -f sa-deploy-trimmed.yaml --env-file .env up -d
/path/to/SSI-5G/docker/5gc_testbed/provision_subscriber.sh

# Bring up gNB, then UE
docker compose -f nr-gnb.yaml --env-file .env up -d
docker compose -f nr-ue.yaml --env-file .env up -d

# Verify: registration + PDU session + real data plane connectivity
docker logs nr_ue
docker exec nr_ue ping -I uesimtun0 -c 4 8.8.8.8
```

## What this validates

Running this produces a full 5G-AKA registration (including an automatic SQN resync, exactly as
real 3GPP procedures do), PDU session establishment, and actual IP connectivity through the UPF's
user plane (`uesimtun0` TUN interface on the UE, `ogstun` on the UPF) — a genuinely working,
standards-compliant 5G SA network, not a toy simulation.

## Relationship to the SSI-based authentication mechanism

This 5G Core runs its **native** primary authentication (5G-AKA via AUSF/UDM), unmodified: we did
not fork Open5GS/UERANSIM to replace AMF's internal authentication with our SSI/threshold-signature
scheme, since that would require non-trivial changes to third-party Go/C code we do not maintain.

What this testbed demonstrates is that a real, standards-compliant 5G Core and RAN can be stood up
and validated on the same infrastructure used for the rest of this work. The SSI-based mechanism
(validated separately — see `docker/run_testbed.sh` and the Mininet-based experiments) is
positioned as an additional authorization layer for network-slice access — conceptually similar to
how the JWT issued by our Authorization Server could gate a UE's access to a slice **after**
primary 5G-AKA authentication has already taken place — rather than a replacement for AMF's
registration procedure. Full AMF-level integration (having AMF itself consume a VC-derived
credential as part of primary authentication) is future work, and would require contributing
changes upstream to Open5GS or a similar Core implementation.
