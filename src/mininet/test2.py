#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.cli import CLI
import os
from dotenv import load_dotenv


# Globals
ues, bbupool, switches = dict(), dict(), dict()
load_dotenv()
N_BBUs = int(os.getenv("N_BBUs"))
N_RRHs = int(os.getenv("N_RRHs"))
N_UEs = int(os.getenv("N_UEs"))
CENTRAL_BBU_IP_1 = os.getenv("CENTRAL_BBU_IP_1")
CENTRAL_BBU_IP_2 = os.getenv("CENTRAL_BBU_IP_2")
AUTHZ_SERVER_IP = os.getenv("AUTHZ_SERVER_IP")
AUTHZ_SERVER_PORT = os.getenv("AUTHZ_SERVER_PORT")
MININET_INTERPRETER_PATH = os.getenv("MININET_INTERPRETER_PATH")
SSI_INTERPRETER_PATH = os.getenv("SSI_INTERPRETER_PATH")
SSI_USER_PATH = os.getenv("SSI_USER_PATH")
SSI_VERIFIER_PATH = os.getenv("SSI_VERIFIER_PATH")
SSI_AUTHZ_SERVER_PATH = os.getenv("SSI_AUTHZ_SERVER_PATH")
VERIFIER_PORT = os.getenv("VERIFIER_PORT")
SSI_INPUT_FOLDER = os.getenv("SSI_INPUT_FOLDER")



def start_authz_server(authz_server):
    authz_server.cmd(f'{SSI_INTERPRETER_PATH} {SSI_AUTHZ_SERVER_PATH} --authz_server_ip {AUTHZ_SERVER_IP} --authz_server_port {AUTHZ_SERVER_PORT} --input_folder {SSI_INPUT_FOLDER} &')
    print(f"*** Authorization server started, logged in logs folder")


def start_vpn_gateway(host):
    host.cmd(f'{MININET_INTERPRETER_PATH} vpn_gateway.py &')
    
    
def start_ssi_user(ue, c_bbu_ip):
    out = ue.cmd(f'{SSI_INTERPRETER_PATH} {SSI_USER_PATH} --verifier_ip {c_bbu_ip} --verifier_port {VERIFIER_PORT} --input_folder {SSI_INPUT_FOLDER} &')
    print(f"*** SSI user started, logged in logs folder")

    
    
def start_ssi_verifier(c_bbu):
    c_bbu.cmd(f'{SSI_INTERPRETER_PATH} {SSI_VERIFIER_PATH} --verifier_port {VERIFIER_PORT} --input_folder {SSI_INPUT_FOLDER} --authz_server_ip {AUTHZ_SERVER_IP} --authz_server_port {AUTHZ_SERVER_PORT} &')
    print(f"*** SSI verifier started, logged in logs folder")


def create_cloud_ran():
    net = Mininet(controller=RemoteController, link=TCLink, switch=OVSSwitch)

    print("*** Adding Remote Ryu Controller")
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)
    
    print("*** Adding switches (including for RRHs and BBUs simulation")
    for i in range(N_RRHs + N_BBUs + 2):
        switches[f"s{i}"] = net.addSwitch(f"s{i}")

    print("*** Adding UEs")
    for i in range(N_UEs):
        ues[f'ue{i}'] = net.addHost(f'ue{i}')
    
    print("*** Adding centralized BBU")
    central_bbu = net.addHost("c_bbu", ip=f"{CENTRAL_BBU_IP_1}/24")
    
    print("*** Adding the authorization server")
    authz_server = net.addHost("authz", ip=f"{AUTHZ_SERVER_IP}/24")
    
    print("*** Creating links: RRHs <-> Fronthaul switch")
    for i in range(1, 6):
        net.addLink(switches[f"s{i}"], switches["s0"], bw=10, delay='1ms')

    print("*** Creating links: BBU Pool <-> Fronthaul switch")
    print("*** Creating links: BBU Pool <-> Central BBU")
    for i in range(6, 9):
        net.addLink(switches[f"s{i}"], switches["s0"], bw=10, delay='1ms')
        net.addLink(switches[f"s{i}"], central_bbu, bw=10, delay='1ms')
        
    print("*** Creating links in the cloud")
    net.addLink(central_bbu, switches["s9"], bw=10, delay='1ms')
    net.addLink(switches["s9"], authz_server, bw=10, delay='1ms')

    print("*** Creating links: UEs <-> RRHs (simulating wireless connection)")
    for i, ue in enumerate(ues): 
        net.addLink(ue, switches[f"s{i % N_RRHs + 1}"], bw=10, delay='1ms') # assegna 2 UE per RRH
    
    central_bbu.setIP(f"{CENTRAL_BBU_IP_1[:-3]}{int(CENTRAL_BBU_IP_1[-3:]) + 1}/24", intf="c_bbu-eth1")
    central_bbu.setIP(f"{CENTRAL_BBU_IP_1[:-3]}{int(CENTRAL_BBU_IP_1[-3:]) + 2}/24", intf="c_bbu-eth2")
    central_bbu.setIP(f"{CENTRAL_BBU_IP_2}/24", intf="c_bbu-eth3")
         
    return net


def get_port_mapping(net, switch):
    switch_port_mapping = {}

    print(f"\n*** Mappa porte switch {switch.name}")
    for intf in switch.intfList():
        if 'lo' in intf.name:   # ignora loopback
            continue
        port_number = switch.ports[intf]
        link = intf.link
        if link:
            node = link.intf1.node if link.intf2.node == switch else link.intf2.node
            switch_port_mapping[node.name] = port_number

    return switch_port_mapping        


def main():
    net = create_cloud_ran()

    try:
        print("*** Starting network")
        net.start()

        for switch in net.switches:
            print("SWITCH:", switch)

        for host in net.hosts:
            print("HOST:", host, host.IP(), host.MAC())

        for link in net.links:
            host1 = link.intf1.name.split("-")[0]
            host2 = link.intf2.name.split("-")[0]
            print(host1, "<->", host2)

        start_authz_server(net.get("authz"))
        # print("*** AAA server successfully started")

        # start_vpn_gateway(net.get("vpn_gate"))
        # print("*** VPN gateway successfully started")

        c_bbu = net.get("c_bbu")
        start_ssi_user(net.get("ue0"), c_bbu.IP())
        start_ssi_verifier(c_bbu)

        CLI(net)

    finally:
        print("*** Stopping network")
        net.stop()



if __name__ == '__main__':
    main()

