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
from interface_utils import verify_turn_on_interfaces

TOPOLOGY = """
# +-------+
# |  ops1 |
# +-------+

# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=openswitch name="Openswitch 2"] ops2

# Links
ops1:if01 -- ops2:if01
"""


IP_ADDR1 = "8.0.0.1"
IP_ADDR2 = "8.0.0.2"

DEFAULT_PL = "8"

SW1_ROUTER_ID = "8.0.0.1"
SW2_ROUTER_ID = "8.0.0.2"

AS_NUM1 = "1"
AS_NUM2 = "2"

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


def configure_route_map_set_weight(dut, routemap, weight):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "set weight " + weight
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def configure_route_map_set_localpref(dut, routemap, as_num, localpref):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "set local-preference " + localpref
    dut(cmd)
    dut(cmd1)
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


def verify_routemap_set_weight(step, switch1, switch2):
    step("\n\n########## Verifying route-map set weight##########\n")

    step("Configuring no router bgp on SW2")
    enternoroutercontext(switch2, AS_NUM2)

    step("Configuring route-map on SW2")
    configure_route_map_set_weight(switch2, "BGP_IN2", "22")

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, AS_NUM2, SW2_ROUTER_ID)

    step("Configuring networks on SW2")
    configure_network(switch2, AS_NUM2, "10.0.0.0/8")

    step("Configuring networks on SW2")
    configure_network(switch2, AS_NUM2, "11.0.0.0/8")

    step("Configuring neighbors on SW2")
    configure_neighbor(switch2, AS_NUM2, IP_ADDR1, AS_NUM1)

    step("Configuring neighbor route-map on SW2")
    configure_neighbor_rmap_in(switch2, AS_NUM2, IP_ADDR1, AS_NUM1, "BGP_IN2")

    exitcontext(switch2)
    wait_for_route(switch2, "10.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "11.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "9.0.0.0", "8.0.0.1")

    dump = switch2("show ip bgp")
    set_weight_flag = False

    lines = dump.split("\n")
    for line in lines:
        if "22" in line and "9.0.0.0" in line:
            set_weight_flag = True

    assert (set_weight_flag is True), "Failed to configure \"set weight\""

    step("### \"set weight\" running succesfully ###\n")


def verify_routemap_set_localpref(step, switch1, switch2):
    step("\n########## Verifying route-map set local-preference##########\n")

    step("Configuring no router bgp on SW2")
    enternoroutercontext(switch2, AS_NUM2)

    localpref = "45"
    step("Configuring route-map on SW2")
    configure_route_map_set_localpref(switch2, "BGP_IN2", AS_NUM2, localpref)

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, AS_NUM2, SW2_ROUTER_ID)

    step("Configuring networks on SW2")
    configure_network(switch2, AS_NUM2, "10.0.0.0/8")

    step("Configuring networks on SW2")
    configure_network(switch2, AS_NUM2, "11.0.0.0/8")

    step("Configuring neighbors on SW2")
    configure_neighbor(switch2, AS_NUM2, IP_ADDR1, AS_NUM1)

    step("Configuring neighbor route-map on SW2")
    configure_neighbor_rmap_in(switch2, AS_NUM2, IP_ADDR1, AS_NUM1, "BGP_IN2")

    exitcontext(switch2)
    wait_for_route(switch2, "10.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "11.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "9.0.0.0", "8.0.0.1")

    dump = switch2("show ip bgp")
    set_localpref_flag = False

    lines = dump.split("\n")
    for line in lines:
        if "45" in line:
            set_localpref_flag = True

    assert set_localpref_flag is True, \
        "Failed to configure \"set local - preference\""
    step("\"set local - preference\" running succesfully")


def configure(step, switch1, switch2):
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

    with switch1.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW1.
        step("Enabling interface1 on SW1")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW1
        ctx.ip_address("%s/%s" % (IP_ADDR1, DEFAULT_PL))

    verify_turn_on_interfaces(switch1, [switch1.ports["if01"]])

    with switch2.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW2.
        step("Enabling interface1 on SW2")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW2
        ctx.ip_address("%s/%s" % (IP_ADDR2, DEFAULT_PL))

    verify_turn_on_interfaces(switch2, [switch2.ports["if01"]])

#    For SW1 and SW2, configure bgp
    step("Configuring router id on SW1")
    configure_router_id(step, switch1, AS_NUM1, SW1_ROUTER_ID)

    step("Configuring networks on SW1")
    configure_network(switch1, AS_NUM1, "9.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, AS_NUM1, IP_ADDR2, AS_NUM2)

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, AS_NUM2, SW2_ROUTER_ID)

    step("Configuring networks on SW2")
    configure_network(switch2, AS_NUM2, "10.0.0.0/8")

    step("Configuring networks on SW2")
    configure_network(switch2, AS_NUM2, "11.0.0.0/8")

    step("Configuring neighbors on SW2")
    configure_neighbor(switch2, AS_NUM2, IP_ADDR1, AS_NUM1)


@mark.timeout(600)
def test_bgp_ft_routemap_weight(topology, step):
    ops1 = topology.get('ops1')
    ops2 = topology.get('ops2')

    assert ops1 is not None
    assert ops2 is not None

    ops1.name = "ops1"
    ops2.name = "ops2"

    configure(step, ops1, ops2)

    verify_routemap_set_weight(step, ops1, ops2)
    verify_routemap_set_localpref(step, ops1, ops2)
