# -*- coding: utf-8 -*-
# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
##########################################################################

"""
OpenSwitch Test for vlan related configurations.
"""

from time import sleep
from pytest import mark

TOPOLOGY = """
# +-------+
# |  ops1 |
# +-------+

# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=openswitch name="Openswitch 2"] ops2
[type=openswitch name="Openswitch 3"] ops3

# Links
ops1:if01 -- ops2:if01
ops2:if02 -- ops3:if01
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

VTYSH_CR = "\r\n"
max_wait_time = 100


def enterconfigshell(dut):
    dut("configure terminal")


def enterroutercontext(dut, as_num):
    enterconfigshell(dut)

    dut("router bgp " + as_num)


def enternoroutercontext(dut, as_num):
    enterconfigshell(dut)

    dut("no router bgp " + as_num)
    exitcontext(dut)


def exitcontext(dut):
    dut("end")


def configure_no_route_map(dut, routemap):
    enterconfigshell(dut)

    cmd = "no route-map " + routemap + " permit 20"
    dut(cmd)
    exitcontext(dut)


def configure_router_id(step, dut, as_num, router_id):
    enterroutercontext(dut, as_num)

    step("Configuring BGP router ID " + router_id)
    dut("bgp router-id " + router_id)
    exitcontext(dut)


def configure_network(dut, as_num, network):
    enterroutercontext(dut, as_num)

    cmd = "network " + network
    dut(cmd)
    exitcontext(dut)


def configure_neighbor(dut, as_num1, network, as_num2):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " remote-as " + as_num2
    dut(cmd)
    exitcontext(dut)


def configure_neighbor_rmap_out(dut, as_num1, network, as_num2, routemap):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " route-map " + routemap + " out"
    dut(cmd)
    exitcontext(dut)


def configure_neighbor_rmap_in(dut, as_num1, network, as_num2, routemap):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " route-map " + routemap + " in"
    dut(cmd)
    exitcontext(dut)


def clear_soft_out_peer_group(dut, group):
    enterconfigshell(dut)

    dut("do clear bgp peer-group " + group + " soft out")
    exitcontext(dut)


def configure_route_map_set_metric(dut, routemap, as_num, metric):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "set metric " + metric
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def configure_route_map_match_metric(dut, routemap, as_num, metric):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "match metric " + metric
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def configure_peer_group(dut, as_num1, group):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + group + " peer-group"
    dut(cmd)
    exitcontext(dut)


def configure_peer_group_member(dut, as_num1, peer_ip, group):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + peer_ip + " peer-group " + group
    dut(cmd)
    exitcontext(dut)


def verify_bgp_routes(dut, network, next_hop):
    dump = dut("show ip bgp")
    routes = dump.split("\r\n")
    for route in routes:
        if network in route and next_hop in route:
            return True
    return False


def wait_for_route(dut, network, next_hop, condition=True):
    for i in range(max_wait_time):
        found = verify_bgp_routes(dut, network, next_hop)
        if found == condition:
            if condition:
                result = "configuration successfull"
            else:
                result = "configuration not successfull"
            print(result)
            return found
        sleep(1)
    print("### Condition not met after %s seconds ###\n" %
          max_wait_time)
    return found


def verify_routemap_set_metric_clear_soft_out_peer_group(step, switch1,
                                                         switch2, switch3):
    step("\n\n########## Verifying route-map set metric test 1"
         " for clear soft out peer group command##########\n")

    metric = "25"

    step("Configuring route-map on SW2")
    configure_route_map_set_metric(switch2, "BGP_OUT", AS_NUM2, metric)

    step("Configuring peer group")
    configure_peer_group(switch2, AS_NUM2, "pGroup")

    step("Adding neighbor 1 to peer group")
    configure_peer_group_member(switch2, AS_NUM2, IP_ADDR1, "pGroup")

    step("Adding neighbor 3 to peer group")
    configure_peer_group_member(switch2, AS_NUM2, IP_ADDR3, "pGroup")

    step("Configuring neighbor route-map on SW2 for peer group")
    configure_neighbor_rmap_out(switch2, AS_NUM2, "pGroup", AS_NUM1,
                                "BGP_OUT")

    clear_soft_out_peer_group(switch2, "pGroup")

    exitcontext(switch1)
    exitcontext(switch2)
    exitcontext(switch3)
    network = neighbor_network_2 = NETWORK_SW2

    next_hop1 = "8.0.0.2"
    next_hop3 = "40.0.0.1"
    found = wait_for_route(switch1, network, next_hop1)

    assert found, "Could not find route (%s -> %s) on %s" % \
        (network, next_hop1, switch1.name)

    found = wait_for_route(switch3, network,
                           next_hop3)

    assert found, "Could not find route (%s -> %s) on %s" % \
        (network, next_hop3, switch3.name)

    metric_str = " 25 "
    set_metric_flag_1 = False
    set_metric_flag_3 = False
    dump = switch1("show ip bgp")
    lines = dump.split("\n")
    for line in lines:
        print(line)
        if neighbor_network_2 in line and metric_str in line:
            set_metric_flag_1 = True

    assert (set_metric_flag_1 is True), "Failure to verify clear bgp " \
                                        "peer group" \
                                        " soft out command on peer 2 " \
                                        "for neighbor %s" % IP_ADDR1
    step("### \"clear bgp peer group soft out\" validated succesfully"
         " on peer 2 for neighbor %s###\n" % IP_ADDR1)

    dump = switch3("show ip bgp")
    lines = dump.split("\n")
    for line in lines:
        if neighbor_network_2 in line and metric_str in line:
            set_metric_flag_3 = True

    assert (set_metric_flag_3 is True), "Failure to verify clear bgp " \
                                        "peer group" \
                                        " soft out command on peer 2 " \
                                        " for neighbor %s" % IP_ADDR3
    step("### \"clear bgp peer group soft out\" validated succesfully"
         " on peer 2 for neighbor %s###\n" % IP_ADDR3)


def configure(step, switch1, switch2, switch3):
    """
     - Configures the IP address in SW1, SW2 and SW3
     - Creates router bgp instance on SW1, SW2 and SW3
     - Configures the router id
     - Configures the network range
     - Configure neighbor
    """

    """
    - Enable the link.
    - Set IP for the switches.
    """
    with switch1.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW1.
        step("Enabling interface1 on SW1")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW1
        ctx.ip_address("%s/%s" % (IP_ADDR1, DEFAULT_PL))

    with switch2.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW2.
        step("Enabling interface1 on SW2")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW2
        ctx.ip_address("%s/%s" % (IP_ADDR2_1, DEFAULT_PL))

    with switch2.libs.vtysh.ConfigInterface("if02") as ctx:
        # Enabling interface 1 SW2.
        step("Enabling interface1 on SW2")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 2 of SW2
        ctx.ip_address("%s/%s" % (IP_ADDR2_2, DEFAULT_PL))

    with switch3.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW3.
        step("Enabling interface1 on SW3")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW3
        ctx.ip_address("%s/%s" % (IP_ADDR3, DEFAULT_PL))

#   For SW1, SW2 and SW3, configure bgp
    step("Configuring router id on SW1")
    configure_router_id(step, switch1, AS_NUM1, SW1_ROUTER_ID)

    step("Configuring networks on SW1")
    configure_network(switch1, AS_NUM1, "11.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, AS_NUM1, IP_ADDR2_1, AS_NUM2)

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, AS_NUM2, SW2_ROUTER_ID)

    step("Configuring networks on SW2")
    configure_network(switch2, AS_NUM2, "15.0.0.0/8")

    step("Configuring neighbor 1 on SW2")
    configure_neighbor(switch2, AS_NUM2, IP_ADDR1, AS_NUM1)

    step("Configuring neighbor 3 on SW2")
    configure_neighbor(switch2, AS_NUM2, IP_ADDR3, AS_NUM3)

    step("Configuring router id on SW3")
    configure_router_id(step, switch3, AS_NUM3, SW3_ROUTER_ID)

    step("Configuring networks on SW3")
    configure_network(switch3, AS_NUM3, "12.0.0.0/8")

    step("Configuring neighbor on SW3")
    configure_neighbor(switch3, AS_NUM3, IP_ADDR2_2, AS_NUM2)


@mark.gate
@mark.timeout(600)
def test_bgp_ft_routemap_metric_clear_peer_group_out(topology, step):
    ops1 = topology.get("ops1")
    ops2 = topology.get("ops2")
    ops3 = topology.get("ops3")

    assert ops1 is not None
    assert ops2 is not None
    assert ops3 is not None

    ops1.name = "ops1"
    ops2.name = "ops2"
    ops3.name = "ops3"

    configure(step, ops1, ops2, ops3)

    verify_routemap_set_metric_clear_soft_out_peer_group(step, ops1,
                                                         ops2, ops3)
