# SSI-5G
This is the repository of the manuscript named _Decentralizing Slice-Specific Authentication and Authorization in Cloud RAN via Threshold-Issued Credentials_.


## Structure
The repo provides the implementation of an emulated Cloud RAN, in which user equipment (UE) devices authenticate to the core network through a mechanism based on **Self-Sovereign Identity (SSI)**. The subsequent authorization, carried out through an authorization server (AS), allows UEs to obtain access to a network slice. In order to avoid verifiable credentials (VCs) being issued by a _Single Point of Failure and Vulnerability_, we modified the classic SSI paradigm so that a consortium of multiple trusted issuers, through a **threshold signature** protocol, signs and issues the VCs.


The VC schema used is represented in the table below.

| expirationDate | isolationLevel | maxPing | minThroughputMbps | plmnId | uptimePercentage | 
|----------------|----------------|---------|-------------------|--------|------------------|
|                |                |         |                   |        |                  |    

The `expirationDate` field indicates the validity period of the credential. The `plmnId` field identifies the operator (_Mobile Network Operator_, MNO) with which the UE has a subscription contract. The remaining fields identify the Quality of Service (QoS) attributes guaranteed to the UE by the subscribed plan.

The project is composed of the following modules.

- `/src/mininet`: emulates the C-RAN in which the authentication and authorization mechanism has been implemented.
- `/src/ssi`: provides the SSI mechanism for exchanging and verifying credentials.
- `/src/tss`: handles the issuance of VCs, signed through a threshold signature protocol.

In turn, the `ssi` module provides the following agents.

- `/src/ssi/user.py`: implements the UE (_holder_ of the SSI paradigm), which provides its own VC to request access to a network resource.
- `/src/ssi/verifier.py`: implements the _Central Unit_ (CU, i.e. _verifier_ of the SSI paradigm), which identifies the UE based on the credential it provides.
- `/src/ssi/authz_server.py`: implements the server that, once authentication is complete, handles authorizing access to the requested resources.



## Setup

A Docker image is available that already contains all the prerequisites (see [Running in Docker](#running-in-docker) - *RECOMMENDED*); alternatively, the project can be run directly on the host by following the instructions below *NOT RECOMMENDED*.

To ensure full compatibility with the `mininet` module, the project must be run on a **native Linux** machine.
Additionally, the following prerequisites are required:

- `go`
- `python 3.8` (later versions have compatibility issues with the `mininet` module).


### Instructions for running the project

1. Assign meaningful values to the environment variables defined in the `.env` file. The version provided by the
repo shows example values.

2. From the project root directory, create a virtual environment.
```
python3.8 -m venv venv
```

3. Activate the virtual environment just created.
```
source venv/bin/activate
```

4. From the project root directory, install the dependencies.
```
pip install -r requirements.txt
```

5. In the `/src/tss` directory, run the issuance of the verifiable credential.
```
python3 issuer.py
```

6. In the `/src/ssi` directory, build the input files for the SSI agents and the AS.
```
python3 init_json.py
```

7. **(Optional)** In the `/src/ssi/input/certs` directory, replace the TLS certificates provided as examples.


8. In the `/src/mininet` directory, start the SDN controller.
```
./start-ryu.sh
```

9. In a new terminal, from the project root directory, start (with elevated privileges) the C-RAN.
The authentication and authorization processes will run automatically, with log files saved in
`/src/mininet/logs`.
```
sudo venv/bin/python3.8 ./src/mininet/net.py
```


### Experiment: impact of inter-issuer latency

To evaluate the effect of network latency between the TSS consortium's issuers on VC issuance time, a dedicated Mininet topology is available (`/src/mininet/net_issuers.py`) that emulates each issuer as an independent network host, connected to a shared switch through a link with configurable latency (an "edge-delay" model: the RTT between any two issuers equals 2×L). For each combination of number of issuers (`ISSUER_N_LIST`) and latency (`ISSUER_LATENCIES_MS`) defined in the `.env` file, the script starts the FROST protocol's Go nodes on the Mininet hosts and orchestrates the key generation and signing process through `/src/tss/issuer_mininet.py`, saving the execution times in `ISSUER_LATENCY_RESULTS_CSV`.

From the `/src/mininet` directory, with elevated privileges:
```
sudo venv/bin/python3.8 ./net_issuers.py
```


### Experiment: single-issuer baseline

To quantify the overhead introduced by threshold signing compared to the traditional model (a single issuer, single point of failure), `/src/tss/issuer_baseline.py` is available, which generates a single Ed25519 key pair and signs the VC directly (no threshold protocol, no peer-to-peer communication). The signed message is built with the same function (`vc_message.py`) used by the threshold scheme, for a comparison on the same payload. Since a single Ed25519 signature takes on the order of tens of microseconds (below the resolution/noise of the wall-clock timer), the reported time is an average over multiple repetitions (default 1000, configurable with `--runs`).

From the `/src/tss` directory:
```
python3 issuer_baseline.py
```
The result is appended to `./logs/baseline_results.csv` with the same schema (`n_signers,latency_ms,time`) as
the file produced by the latency experiment, so that `plot_latency.py --baseline_csv logs/baseline_results.csv`
automatically overlays it as a horizontal reference line.


### Experiment: scalability under concurrent UEs

The original Network SSI Verifier handled one UE session at a time (ZMQ REP socket): a second incoming connection
while the first was still in progress would have corrupted the protocol state, as messages would have interleaved
on the same socket. The verifier has therefore been extended to a ZMQ ROUTER socket
(`communication.ConcurrentVerifierSocket`) that demultiplexes sessions by identity and handles one per thread
(`verifier.handle_ue`); similarly, the Authorization Server now uses `ThreadingHTTPServer` with an increased
backlog instead of the original single-threaded server. This allows measuring the system's actual scalability
(success rate, throughput, latency) as the number of concurrently authenticating UEs grows, rather than simply
repeating a single UE's registration.

The `/src/mininet/net_scalability.py` script starts M concurrent Mininet UEs against a single verifier/authz-server
pair, for each value of M in `SCALABILITY_UE_LIST`, saving the success rate, throughput, and average/p95 latency
in `SCALABILITY_RESULTS_CSV`.

From the `/src/mininet` directory, with elevated privileges (requires the SDN controller already running):
```
sudo venv/bin/python3.8 ./net_scalability.py
python3 plot_scalability.py --csv logs/scalability_results.csv
```

**Methodological note**: all M UEs share the same credential pair (`user_input.json` is generated only once by
`init_json.py`), so the experiment measures the system's ability to serve concurrent sessions with valid
credentials, not the heterogeneity of a population of distinct identities.


### Experiment: real testbed (non-emulated)

The previous experiments run on Mininet, an SDN emulation framework: to verify that the results are not an
artifact of the emulation (virtual links, forwarding via Open vSwitch), `/docker/run_testbed.sh` deploys each
component (issuer consortium, Network SSI Verifier, Authorization Server, UE) as **separate Docker containers on
a real bridge network**, with real independent network namespaces and forwarding via the Linux kernel's
veth/bridge/iptables, instead of through the Mininet emulator. This is the same kind of containerized deployment
with which a Cloud RAN's network functions would actually run in production.

```
./docker/run_testbed.sh [N_ISSUER]   # default 3
```

The script builds the TSS node (into `node_testbed`, so as not to touch the `node` binary tracked in git), starts
N issuer containers, orchestrates threshold key generation and signing (`issuer_docker.py`), generates the
SSI/authz inputs, starts the verifier and authz-server containers, runs a one-shot UE against them and prints the
relevant logs, then performs full teardown.

**Validation result**: the end-to-end time of the SSI handshake alone measured on this real testbed (~11-13ms) is
consistent with (in fact lower than) the one measured on Mininet in the conference paper (Table I, 70-210ms) —
the additional overhead on Mininet is therefore due to the emulator's OVS/tc-netem forwarding path, not to the
protocol itself; the numbers reported with Mininet are therefore, if anything, a conservative (pessimistic)
estimate of real-world performance.

Building this testbed also surfaced two real bugs, previously masked by the fact that Mininet forcibly kills all
processes at teardown instead of letting them exit naturally: (1) the RAM monitoring processes
(`multiprocessing.Process`) were not daemons, causing a deadlock when a process had to terminate on its own; (2)
in the authorization server's exception handler, the HTTP response body was written before `end_headers()`,
corrupting the HTTP framing on error. Both have been fixed.


### Experiment: real 5G SA testbed (Open5GS + UERANSIM)

In addition to the containerized testbed above (which only validates that the timings are not a Mininet
artifact), `/docker/5gc_testbed/` documents how to validate the work on a **real, 3GPP-compliant 5G Core and RAN**
(Open5GS + UERANSIM), directly addressing some reviewers' request for an evaluation based on a realistic 5G stack.
See `/docker/5gc_testbed/README.md` for the complete instructions and `example_ue_registration.md` for evidence of
a successful end-to-end UE registration, PDU session, and data connectivity.

The 5G Core runs its own native primary authentication (5G-AKA); this project's SSI mechanism has not been
integrated at the AMF level (which would require modifying third-party Go/C code that we do not maintain), but is
positioned conceptually as an additional authorization layer for slice access, complementary to 5G-AKA
authentication rather than a replacement for it.

`/docker/5gc_testbed/measure_overhead.sh` measures the overhead introduced by the SSI mechanism relative to
native 5G-AKA registration alone (latency, signaling volume, RAM footprint), using protocol-level timestamps (not
the timing of Docker invocations, which is dominated by container startup noise). Result summarized in
`overhead_report.md`: SSI authorization adds ~19ms, about 8% more than the ~230ms of native 5G registration.


## Running in Docker

The provided Docker image (`Dockerfile`) encapsulates all the prerequisites (Python 3.8, Go, Mininet, Open
vSwitch) and is used to run both the full C-RAN (`net.py`) and the inter-issuer latency experiment
(`net_issuers.py`).

**Host prerequisites** (cannot be removed by containerizing, because Mininet creates network namespaces and uses
Open vSwitch, which depend on the kernel shared with the host):
- the `openvswitch` and `sch_netem` kernel modules loaded (`sudo modprobe openvswitch sch_netem`);
- the container must run with `--privileged` (or at least `--cap-add=NET_ADMIN --cap-add=SYS_ADMIN`).

### Build
```
docker build -t ssi-5g .
```

### Interactive run
```
cp .env.docker.example .env.docker   # customize values if needed
docker run --rm -it --privileged --cap-add=NET_ADMIN --cap-add=SYS_ADMIN \
  -v /lib/modules:/lib/modules:ro \
  --env-file .env.docker \
  ssi-5g
```
Alternatively, with `docker compose up -d && docker compose exec ssi-5g bash` (requires first running
`cp .env.docker.example .env.docker`).

Inside the container the project is located at `/opt/ssi-5g` with the venv already set up and active
(`source venv/bin/activate` is run automatically by the entrypoint); from there you run the same commands
described in the previous sections (e.g. `python3.8 src/tss/issuer.py --n_signers N`,
`python3.8 src/mininet/net_issuers.py`, `python3.8 src/mininet/net.py` after starting `start-ryu.sh` in the
background).

**Note**: the `.env` file tracked in the repository contains absolute paths intended for running on the host
(e.g. `/home/.../venv/bin/python3.8`); `.env.docker.example` provides the equivalent in-container paths
(`/opt/ssi-5g/...`) and should be used instead of `.env` when working in Docker.


### .env file
`SUB_PLMN_ID`: value (string) of `plmnId` to insert into the generated VC

`SUB_MAX_PING`: value (integer) of `maxPing` to insert into the generated VC

`SUB_MIN_THORUGHPUT_MBPS`: value (integer) of `minThroughputMbps` to insert into the generated VC

`SUB_UPTIME_PERCENTAGE`: value (integer) of `uptimePercentage` to insert into the generated VC

`SUB_ISOLATION_LEVEL`: value (integer) of `isolationLevel` to insert into the generated VC

`REQ_SITE_ID`: identifier (integer) of the resource pool where the network slice the UE wants to access is located

`REQ_SLICE_ID`: identifier (integer) of the network slice the UE wants to access

`N_BBUs`: number of decentralized BBUs to include in the emulated C-RAN

`N_RRHs`: number of RRHs to include in the emulated C-RAN

`N_UEs`: number of UEs to include in the emulated C-RAN

`ISSUER_BASE_PORT`: port number from which to instantiate the _n_ signer processes

`CENTRAL_BBU_IP_1`: IP address of the CU's first network interface

`CENTRAL_BBU_IP_2`: IP address of the CU's second network interface

`AUTHZ_SERVER_IP`: IP address of the authorization server

`AUTHZ_SERVER_PORT`: port number of the authorization server

`MININET_INTERPRETER_PATH`: path of the Python interpreter to use in the `mininet` module (default `/venv/bin/python3.8`)

`SSI_INTERPRETER_PATH`: path of the Python interpreter to use in the `ssi` module (default `/venv/bin/python3.8`)

`SSI_USER_PATH`: path of the `user.py` script (default `/src/ssi/user.py`)

`SSI_VERIFIER_PATH`: path of the `verifier.py` script (default `/src/ssi/verifier.py`)

`SSI_AUTHZ_SERVER_PATH`: path of the `authz_server.py` script (default `/src/ssi/authz_server.py`)

`VERIFIER_PORT`: verifier port

`SSI_INPUT_FOLDER`: path of the folder containing the input files for the SSI agents (default `/src/ssi/inputs`)

`ISSUER_N_LIST`: comma-separated list of N values (number of issuers) to test in the latency experiment (default `5,10,20`)

`ISSUER_LATENCIES_MS`: comma-separated list of link latencies (in ms) to test between issuers in the dedicated Mininet topology (default `0,5,20,50,100`)

`ISSUER_LATENCY_RESULTS_CSV`: path of the CSV file where the results of the inter-issuer latency experiment are saved (default `../tss/logs/latency_results.csv`)




## Authors and contacts

| Author              | Email address                  |
|---------------------|--------------------------------|
| Biagio Boi          | bboi@unisa.it                  |
| Francesco Giorgione | francesco.giorgione01@gmail.com|