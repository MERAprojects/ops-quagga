# (c) Copyright 2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from time import sleep
import pytest
from interface_utils import verify_turn_on_interfaces

TOPOLOGY = """
#
# +-------+     +-------+     +-------+
# |  sw1  <----->  sw2  <----->  sw3  |
# +-------+     +-------+     +-------+
#

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=openswitch name="Switch 3"] sw3

# Links
sw1:if01 -- sw2:if01
sw2:if02 -- sw3:if01

# switch 1 configuration
# ----------------------

#  router bgp 1
#  bgp router-id 8.0.0.1
#  network 11.0.0.0/8
#  neighbor 8.0.0.2 remote-as 2
#  neighbor 8.0.0.2 route-map 1 in

#  interface 1
#  no shutdown
#  ip address 8.0.0.1/8

# switch 2 configuration
# ----------------------

#  router bgp 2
#  bgp router-id 8.0.0.2
#  network 15.0.0.0/8
#  neighbor 8.0.0.1 remote-as 1
#  neighbor 40.0.0.2 remote-as 3

# interface 1
#     no shutdown
#     ip address 8.0.0.2/8
# interface 2
#     no shutdown
#     ip address 40.0.0.1/8

#switch 3 configuration
# ----------------------

#  router bgp 3
#  bgp router-id 8.0.0.3
#  network 12.0.0.0/8
#  neighbor 40.0.0.1 remote-as 2

# interface 1
#     no shutdown
#     ip address 40.0.0.2/8
"""

IP_ADDR1 = "8.0.0.1"
IP_ADDR2_1 = "8.0.0.2"
IP_ADDR2_2 = "40.0.0.1"
IP_ADDR3 = "40.0.0.2"
DEFAULT_PL = "8"

SW1_ROUTER_ID = "8.0.0.1"
SW2_ROUTER_ID = "8.0.0.2"
SW3_ROUTER_ID = "8.0.0.3"


NETWORK_SW1 = "11.0.0.0/8"
NETWORK_SW2 = "15.0.0.0/8"
NETWORK_SW3 = "12.0.0.0/8"

AS_NUM1 = "1"
AS_NUM2 = "2"
AS_NUM3 = "3"

VTYSH_CR = '\r\n'
MAX_WAIT_TIME = 100


def verify_bgp_routes(dut, network, next_hop):
    dump = dut("show ip bgp")
    routes = dump.split(VTYSH_CR)
    for route in routes:
        if network in route and next_hop in route:
            return True
    return False


def wait_for_route(dut, network, next_hop, condition=True):
    for i in range(MAX_WAIT_TIME):
        found = verify_bgp_routes(dut, network, next_hop)
        if found == condition:
            if condition:
                result = "Configuration successfull"
            else:
                result = "Configuration not successfull"
            print(result)
            return found
        sleep(1)
    print("### Condition not met after %s seconds ###\n" % MAX_WAIT_TIME)
    return found


def clearsoftoutasn(dut, asn):
    dut("clear bgp " + asn + " soft out")


def configure_route_map_set_metric(dut, routemap, as_num, metric):
    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "set metric " + metric
    dut("configure terminal")
    dut(cmd)
    dut(cmd1)
    dut("end")


def configure_route_map_match_metric(dut, routemap, as_num, metric):
    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "match metric " + metric
    dut("configure terminal")
    dut(cmd)
    dut(cmd1)
    dut("end")


def configure_router_id(dut, as_num, router_id):
    dut("configure terminal")
    dut("router bgp %s" % as_num)
    print("Configuring BGP router ID " + router_id)
    dut("bgp router-id " + router_id)
    dut("end")


def configure_network(dut, as_num, network):
    dut("configure terminal")
    dut("router bgp %s" % as_num)
    cmd = "network " + network
    dut(cmd)
    dut("end")


def configure_neighbor(dut, as_num1, network, as_num2):
    dut("configure terminal")
    dut("router bgp %s" % as_num1)
    cmd = "neighbor " + network + " remote-as " + as_num2
    dut(cmd)
    dut("end")


def configure_no_route_map(dut, routemap):
    dut("configure terminal")
    cmd = "no route-map " + routemap + " permit 20"
    dut(cmd)
    dut("end")


def configure_neighbor_rmap_out(dut, as_num1, network, as_num2, routemap):
    dut("configure terminal")
    dut("router bgp %s" % as_num1)
    cmd = "neighbor " + network + " route-map " + routemap + " out"
    dut(cmd)
    dut("end")


def configure_peer_group(dut, as_num1, group):
    dut("configure terminal")
    dut("router bgp %s" % as_num1)
    cmd = "neighbor " + group + " peer-group"
    dut(cmd)
    dut("end")


def configure_peer_group_member(dut, as_num1, peer_ip, group):
    dut("configure terminal")
    dut("router bgp %s" % as_num1)
    cmd = "neighbor " + peer_ip + " peer-group "+group
    dut(cmd)
    dut("end")


def configure_neighbor_rmap_in(dut, as_num1, network, as_num2, routemap):
    dut("configure terminal")
    dut("router bgp %s" % as_num1)
    cmd = "neighbor " + network + " route-map "+routemap+" in"
    dut(cmd)
    dut("end")


def verify_routemap_set_metric_clear_soft_out_as(sw1, sw2, sw3):
    print("\n\n########## Verifying route-map set metric test 1"
          " for clear soft out as command##########\n")
    metric = "10"

    print("Configuring route-map on SW2")
    configure_route_map_set_metric(sw2, "BGP_OUT", AS_NUM2, metric)

    print("Configuring route context on SW2")
    sw2("configure terminal")
    sw2("router bgp " + AS_NUM2)
    sw2("end")

    print("Configuring neighbor route-map on SW2 for peer 1")
    configure_neighbor_rmap_out(sw2, AS_NUM2, IP_ADDR1, AS_NUM1, "BGP_OUT")

    print("Configuring neighbor route-map on SW2 for peer 3")
    configure_neighbor_rmap_out(sw2, AS_NUM2, IP_ADDR3, AS_NUM3, "BGP_OUT")

    clearsoftoutasn(sw2, AS_NUM1)
    clearsoftoutasn(sw2, AS_NUM3)

    network = neighbor_network_2 = NETWORK_SW2
    metric_str = ' 10 '
    set_metric_flag_1 = False
    set_metric_flag_3 = False
    next_hop1 = "8.0.0.2"
    next_hop3 = "40.0.0.1"

    found = wait_for_route(sw1, network, next_hop1)

    assert found, "Could not find route (%s -> %s) on %s" % \
        (network, next_hop1, sw1.name)

    found = wait_for_route(sw3, network, next_hop3)

    assert found, "Could not find route (%s -> %s) on %s" % \
        (network, next_hop3, sw3.name)

    dump = sw1("sh ip bgp")
    lines = dump.split('\n')
    for line in lines:
        print(line)
        if neighbor_network_2 in line and metric_str in line:
            set_metric_flag_1 = True

    assert set_metric_flag_1, "Failure to verify clear bgp as soft out command \
                               on peer 2 for neighbor %s" % IP_ADDR1
    print("### 'clear bgp as soft out' validated succesfully "
          "on peer 2 for neighbor %s###\n" % IP_ADDR1)

    dump = sw3("sh ip bgp")
    lines = dump.split('\n')
    for line in lines:
        print(line)
        if neighbor_network_2 in line and metric_str in line:
            set_metric_flag_3 = True

    assert set_metric_flag_3, "Failure to verify clear bgp as soft out command \
                               on peer 2 for neighbor %s" % IP_ADDR3
    print("### 'clear bgp as soft out' validated succesfully "
          "on peer 2 for neighbor %s###\n" % IP_ADDR3)


def configure(sw1, sw2, sw3):
    '''
     - Configures the IP address in SW1, SW2 and SW3
     - Creates router bgp instance on SW1, SW2 and SW3
     - Configures the router id
     - Configures the network range
     - Configure neighbor
    '''

    '''
    - Enable the link.
    - Set IP for the switches.
    '''
    # Enabling interface 1 SW1.
    print("Enabling interface1 on SW1")
    sw1p1 = sw1.ports['if01']
    sw1("configure terminal")
    sw1("interface {sw1p1}".format(**locals()))
    sw1("no shutdown")

    # Assigning an IPv4 address on interface 1 of SW1
    print("Configuring IPv4 address on link 1 SW1")
    sw1("ip address %s/%s" % (IP_ADDR1, DEFAULT_PL))
    sw1("end")

    verify_turn_on_interfaces(sw1, [sw1.ports["if01"]])

    # Enabling interface 1 SW2
    print("Enabling interface1 on SW2")
    sw2p1 = sw2.ports['if01']
    sw2("configure terminal")
    sw2("interface {sw2p1}".format(**locals()))
    sw2("no shutdown")

    # Assigning an IPv4 address on interface 1 for link 1 SW2
    print("Configuring IPv4 address on link 1 SW2")
    sw2("ip address %s/%s" % (IP_ADDR2_1, DEFAULT_PL))
    sw2("end")

    # Enabling interface 2 SW2
    print("Enabling interface 2 on SW2")
    sw2p2 = sw2.ports['if02']
    sw2("configure terminal")
    sw2("interface {sw2p2}".format(**locals()))
    sw2("no shutdown")

    # Assigning an IPv4 address on interface 2 for link 2 SW2
    print("Configuring IPv4 address on link 2 SW2")
    sw2("ip address %s/%s" % (IP_ADDR2_2, DEFAULT_PL))
    sw2("end")

    ports = [sw2.ports["if01"], sw2.ports["if02"]]
    verify_turn_on_interfaces(sw2, ports)

    # Enabling interface 1 SW3
    print("Enabling interface 1 on SW3")
    sw3p1 = sw3.ports['if01']
    sw3("configure terminal")
    sw3("interface {sw3p1}".format(**locals()))
    sw3("no shutdown")

    # Assigning an IPv4 address on interface 1 for link 2 SW3
    print("Configuring IPv4 address on link 2 SW3")
    sw3("ip address %s/%s" % (IP_ADDR3, DEFAULT_PL))
    sw3("end")

    verify_turn_on_interfaces(sw3, [sw3.ports["if01"]])

    # For SW1, SW2 and SW3, configure bgp
    print("Configuring route context on SW1")
    sw1("configure terminal")
    sw1("router bgp " + AS_NUM1)
    sw1("end")

    print("Configuring router id on SW1")
    configure_router_id(sw1, AS_NUM1, SW1_ROUTER_ID)
    print("Configuring networks on SW1")
    configure_network(sw1, AS_NUM1, "11.0.0.0/8")
    print("Configuring neighbors on SW1")
    configure_neighbor(sw1, AS_NUM1, IP_ADDR2_1, AS_NUM2)

    print("Configuring route context on SW2")
    sw2("configure terminal")
    sw2("router bgp " + AS_NUM2)
    sw2("end")
    print("Configuring router id on SW2")
    configure_router_id(sw2, AS_NUM2, SW2_ROUTER_ID)
    print("Configuring networks on SW2")
    configure_network(sw2, AS_NUM2, "15.0.0.0/8")
    print("Configuring neighbor 1 on SW2")
    configure_neighbor(sw2, AS_NUM2, IP_ADDR1, AS_NUM1)
    print("Configuring neighbor 3 on SW2")
    configure_neighbor(sw2, AS_NUM2, IP_ADDR3, AS_NUM3)

    print("Configuring route context on SW3")
    sw3("configure terminal")
    sw3("router bgp " + AS_NUM3)
    sw3("end")
    print("Configuring router id on SW3")
    configure_router_id(sw3, AS_NUM3, SW3_ROUTER_ID)
    print("Configuring networks on SW3")
    configure_network(sw3, AS_NUM3, "12.0.0.0/8")
    print("Configuring neighbor on SW3")
    configure_neighbor(sw3, AS_NUM3, IP_ADDR2_2, AS_NUM2)


@pytest.mark.timeout(600)
def test_bgp_metric_clear_as_out_configuration(topology, step):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None

    configure(sw1, sw2, sw3)
    verify_routemap_set_metric_clear_soft_out_as(sw1, sw2, sw3)
