# SSI-5G — containerized environment for the Mininet-based Cloud RAN emulation,
# the SSI authentication/authorization agents and the TSS issuer consortium.
#
# Mininet creates network namespaces, veth pairs and OVS bridges, so the
# resulting container MUST be run with elevated privileges on the host
# (see README.md, "Esecuzione in Docker" for the exact `docker run` flags
# and host kernel prerequisites: openvswitch and sch_netem kernel modules).
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive \
    GO_VERSION=1.24.6

# --- System dependencies -----------------------------------------------
# python3.8: required for Mininet compatibility (see README).
# openvswitch-switch, iproute2, ethtool, socat, net-tools, iputils-ping,
# traceroute, procps: runtime dependencies of Mininet/TCLink.
# The `mininet` apt package is only used to obtain the `mnexec` helper
# binary (a small C wrapper Mininet needs for cgroup/namespace handling
# that PyPI's pure-Python `mininet` package below does not ship); the
# actual Python API used at runtime is the newer one from requirements.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.8 python3.8-venv python3-pip \
        openvswitch-switch mininet \
        iproute2 iputils-ping traceroute net-tools ethtool socat procps \
        build-essential git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- Go toolchain (pinned; go.mod requires >= 1.24) ---------------------
RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tar.gz \
    && tar -C /usr/local -xzf /tmp/go.tar.gz \
    && rm /tmp/go.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"

WORKDIR /opt/ssi-5g
COPY . .

# --- Python environment --------------------------------------------------
# `mininet` is installed from PyPI (pure source, drives the OVS/OS tools
# installed above), so the venv does not need --system-site-packages.
RUN python3.8 -m venv venv \
    && venv/bin/pip install --upgrade pip \
    && venv/bin/pip install "setuptools==57.5.0" wheel \
    && venv/bin/pip install -r requirements.txt

# --- Build the TSS node binary -------------------------------------------
RUN cd src/tss && go build -o node ./main.go

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
