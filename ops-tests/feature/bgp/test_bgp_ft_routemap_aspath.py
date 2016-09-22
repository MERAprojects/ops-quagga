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

from pytest import mark
from time import sleep

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


ip_addr1 = "8.0.0.1"
ip_addr2 = "8.0.0.2"

default_pl = "8"

sw1_router_id = "8.0.0.1"
sw2_router_id = "8.0.0.2"

as_num1 = "1"
as_num2 = "2"

vtysh_cr = "\r\n"
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


def configure_route_map_set_aspath(dut, routemap, as_num):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "set as-path prepend " + as_num + " " + as_num
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def configure_route_map_match_aspath(dut, routemap, as_num):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "match as-path " + as_num
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


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

    cmd = "neighbor "+network+" remote-as "+as_num2
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


def verify_bgp_routes(dut, network, next_hop):
    dump = dut("show ip bgp")
    routes = dump.split(vtysh_cr)
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
        step("Configuring IPv4 address on link 1 SW1")
        ctx.ip_address("%s/%s" % (ip_addr1, default_pl))

    with switch2.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW2.
        step("Enabling interface1 on SW2")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW2
        step("Configuring IPv4 address on link 1 SW2")
        ctx.ip_address("%s/%s" % (ip_addr2, default_pl))

    # For SW1 and SW2, configure bgp
    step("Configuring router id on SW1")
    configure_router_id(step, switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "9.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, as_num1, ip_addr2, as_num2)

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, as_num2, sw2_router_id)

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "10.0.0.0/8")

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "11.0.0.0/8")

    step("Configuring neighbors on SW2")
    configure_neighbor(switch2, as_num2, ip_addr1, as_num1)


def verify_routemap_set_aspath_prepend(step, switch1, switch2):
    step("\n########## Verifying route-map set as-path prepend##########\n")

    step("Configuring no router bgp")
    enternoroutercontext(switch1, as_num1)

    step("Configuring route-map on SW1")
    configure_route_map_set_aspath(switch1, "BGP_OUT", as_num1)

    step("Configuring router id on SW1")
    configure_router_id(step, switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "9.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, as_num1, ip_addr2, as_num2)

    step("Configuring neighbor route-map on SW1")
    configure_neighbor_rmap_out(switch1, as_num1, ip_addr2, as_num2, "BGP_OUT")

    exitcontext(switch2)

    wait_for_route(switch2, "10.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "11.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "9.0.0.0", "8.0.0.1")

    neighbor_network = "9.0.0.0"
    set_aspath_str = as_num1 + " " + as_num1 + " " + as_num1
    network_p1 = ip_addr1
    set_aspath_flag = False

    dump = switch2("sh ip bgp")

    lines = dump.split("\n")
    for line in lines:
        if (neighbor_network in line and set_aspath_str in line and
           network_p1 in line):
            set_aspath_flag = True
    assert (set_aspath_flag is True), "Failed to configure set as-path "
    step("### \"set as-path prepend\" running succesfully ###\n")


def verify_routemap_match_aspath(step, switch1, switch2):
    step("\n########## Verifying route-map match as-path prepend##########\n")

    step("Configuring no router bgp")
    enternoroutercontext(switch1, as_num1)

    step("Configuring route-map on SW1")
    configure_route_map_set_aspath(switch1, "BGP_OUT", as_num1)

    step("Configuring router id on SW1")
    configure_router_id(step, switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "9.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, as_num1, ip_addr2, as_num2)

    step("Configuring neighbor route-map on SW1")
    configure_neighbor_rmap_out(switch1, as_num1, ip_addr2, as_num2, "BGP_OUT")

    step("Configuring no router bgp")
    enternoroutercontext(switch2, as_num2)

    step("Configuring route-map on SW2")
    configure_route_map_match_aspath(switch2, "BGP_IN", as_num1)

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, as_num2, sw2_router_id)

    step("Configuring route-map on SW2")
    configure_route_map_match_aspath(switch2, "BGP_IN", as_num1)

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, as_num2, sw2_router_id)

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "10.0.0.0/8")

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "11.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch2, as_num2, ip_addr1, as_num1)

    step("Configuring neighbor route-map on SW2")
    configure_neighbor_rmap_out(switch2, as_num2, ip_addr1, as_num1, "BGP_IN")

    exitcontext(switch2)

    wait_for_route(switch2, "10.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "11.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "9.0.0.0", "8.0.0.1")

    neighbor_network = "9.0.0.0"
    match_aspath_str = as_num1 + " " + as_num1 + " " + as_num1
    network_p1 = ip_addr1
    match_aspath_flag = False

    dump = switch2("sh ip bgp")

    lines = dump.split("\n")
    for line in lines:
        if (neighbor_network in line and match_aspath_str in line and
           network_p1 in line):
            match_aspath_flag = True
    assert (match_aspath_flag is True), "Failed to configure match as-path "

    step("### \"match as-path\" running succesfully ###\n")


@mark.gate
@mark.timeout(600)
def test_bgp_ft_routemap_aspath(topology, step):
    ops1 = topology.get('ops1')
    ops2 = topology.get('ops2')

    assert ops1 is not None
    assert ops2 is not None

    ops1.name = "ops1"
    ops2.name = "ops2"

    configure(step, ops1, ops2)
    verify_routemap_set_aspath_prepend(step, ops1, ops2)
    verify_routemap_match_aspath(step, ops1, ops2)
