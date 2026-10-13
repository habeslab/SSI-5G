#!/bin/bash
# Starts the Open vSwitch daemons required by Mininet (there is no systemd
# inside the container, so the apt postinst hooks that would normally do
# this never ran) and then hands off control to the requested command.
set -e

mkdir -p /var/run/openvswitch

if [ ! -S /var/run/openvswitch/db.sock ]; then
    if [ ! -f /etc/openvswitch/conf.db ]; then
        ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
    fi
    ovsdb-server /etc/openvswitch/conf.db \
        --remote=punix:/var/run/openvswitch/db.sock \
        --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
        --pidfile --detach
    ovs-vsctl --no-wait init
fi

if ! pgrep -x ovs-vswitchd > /dev/null; then
    ovs-vswitchd --pidfile --detach
fi

# Activate the project virtualenv for any interactive/child process.
source /opt/ssi-5g/venv/bin/activate

exec "$@"
