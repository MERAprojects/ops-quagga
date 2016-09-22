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
# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=openswitch name="Openswitch 2"] ops2
[type=openswitch name="Openswitch 3"] ops3

# Links
ops1:if01 -- ops2:if01
ops2:if02 -- ops3:if01
"""


ip_addr1 = "7.0.0.1"
ip_addr2 = "7.0.0.2"
ip_addr3 = "8.0.0.2"
ip_addr4 = "8.0.0.3"

default_pl = "8"

sw2_router_id = "8.0.0.2"
sw3_router_id = "8.0.0.3"

as_num1 = "1"
as_num2 = "2"

vtysh_cr = "\r\n"
max_wait_time = 100


def enterconfigshell(dut):
    dut("configure terminal")


def enterroutercontext(dut, as_num):
    enterconfigshell(dut)
    dut("router bgp " + as_num)


def exitcontext(dut):
    dut("end")


def configure_static_route(dut, network, nexthop):
    enterconfigshell(dut)

    cmd = "ip route " + network + " " + nexthop
    dut(cmd)
    exitcontext(dut)


def configure_route_map(dut, routemap):
    enterconfigshell(dut)

    cmd = "ip prefix-list BGP_PList seq 10 permit any"
    dut(cmd)
    cmd = "route-map " + routemap + " permit 20"
    dut(cmd)
    dut("match ip address prefix-list BGP_PList")
    dut("exit")
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


def configure_redistribute(dut, as_num, route_type):
    enterroutercontext(dut, as_num)

    dut("redistribute " + route_type)
    exitcontext(dut)


def configure_redistribute_rmap(dut, as_num, route_type, routemap):
    enterroutercontext(dut, as_num)

    cmd = "redistribute " + route_type + " route-map " + routemap
    dut(cmd)
    exitcontext(dut)


def configure_neighbor(dut, as_num1, network, as_num2):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " remote-as " + as_num2
    dut(cmd)
    exitcontext(dut)


def configure_neighbor_rmap(dut, as_num1, network, as_num2, routemap):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " route-map " + routemap + " out"
    dut(cmd)
    exitcontext(dut)


def verify_bgp_routes(dut, network, next_hop):
    dump = dut("show ip bgp")
    routes = dump.split(vtysh_cr)
    for route in routes:
        if network in route and next_hop in route:
            return True
    return False


def wait_for_route(step, dut, network, next_hop, condition=True):
    for i in range(max_wait_time):
        found = verify_bgp_routes(dut, network, next_hop)
        if found == condition:
            if condition:
                result = "Redistribute configuration successfull"
            else:
                result = "Redistribute configuration not successfull"
            step(result)
            return found
        sleep(1)
    step("### Condition not met after %s seconds ###\n" %
         max_wait_time)
    return found


def configure(step, switch1, switch2, switch3):
    """
     - Configures the IP address in SW1, SW2 and SW3
     - Creates router bgp instance on SW1 and SW2
     - Configures the router id
     - Configures the network range
     - Configure redistribute and neighbor
    """

    """
    - Enable the link.
    - Set IP for the switches.
    """
    # Enabling interface 1 SW1.
    with switch1.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW1.
        step("Enabling interface1 on SW1")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW1
        step("Configuring IPv4 address on link 1 SW1")
        ctx.ip_address("%s/%s" % (ip_addr1, default_pl))

    with switch2.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW2.
        step("Enabling interface1 on SW2")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW2
        step("Configuring IPv4 address on link 1 SW2")
        ctx.ip_address("%s/%s" % (ip_addr2, default_pl))

    with switch2.libs.vtysh.ConfigInterface("if02") as ctx:
        # Enabling interface 2 SW2.
        step("Enabling interface2 on SW2")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 2 of SW2
        step("Configuring IPv4 address on link 2 SW2")
        ctx.ip_address("%s/%s" % (ip_addr3, default_pl))

    with switch3.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW3.
        step("Enabling interface1 on SW3")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW3
        step("Configuring IPv4 address on link 1 SW3")
        ctx.ip_address("%s/%s" % (ip_addr4, default_pl))

    """
    For SW2 and SW3, configure bgp
    """
    step("Configuring static routes on SW2")
    configure_static_route(switch2, "12.0.0.0/8", "7.0.0.1")

    step("Configuring route-map routes on SW2")
    configure_route_map(switch2, "BGP_Rmap")

    step("Configuring router-id on SW2")
    configure_router_id(step, switch2, as_num1, sw2_router_id)

    step("Configuring networks on SW2")
    configure_network(switch2, as_num1, "10.0.0.0/8")

    step("Configuring redistribute configuration on SW2")
    configure_redistribute(switch2, as_num1, "connected")

    step("Configuring redistribute route-map configuration on SW2")
    configure_redistribute_rmap(switch2, as_num1, "static", "BGP_Rmap")

    step("Configuring bgp neighbor on SW2")
    configure_neighbor(switch2, as_num1, ip_addr4, as_num2)

    step("Applying route-map to bgp neighbor on SW2")
    configure_neighbor_rmap(switch2, as_num1, ip_addr4, as_num2, "BGP_Rmap")

    exitcontext(switch2)

    step("Configuring router-id on SW3")
    configure_router_id(step, switch3, as_num2, sw3_router_id)

    step("Configuring networks on SW2")
    configure_network(switch3, as_num2, "19.0.0.0/8")

    configure_neighbor(switch3, as_num2, ip_addr3, as_num1)

    exitcontext(switch3)


@mark.gate
@mark.timeout(600)
def test_bgp_ft_redistribute(topology, step):
    ops1 = topology.get('ops1')
    ops2 = topology.get('ops2')
    ops3 = topology.get('ops3')

    assert ops1 is not None
    assert ops2 is not None
    assert ops3 is not None

    ops1.name = "ops1"
    ops2.name = "ops2"
    ops3.name = "ops3"

    configure(step, ops1, ops2, ops3)

    step("Verifying redistribute configuration")
    wait_for_route(step, ops2, "7.0.0.0", "0.0.0.0")
    wait_for_route(step, ops2, "8.0.0.0", "0.0.0.0")
    wait_for_route(step, ops2, "12.0.0.0", "7.0.0.1")
