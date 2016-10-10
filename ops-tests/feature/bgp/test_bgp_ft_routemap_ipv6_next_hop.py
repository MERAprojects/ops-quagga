# -*- coding: utf-8 -*-
# (C) Copyright 2015 Hewlett Packard Enterprise Development LP
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
from interface_utils import verify_turn_on_interfaces

TOPOLOGY = """
# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=openswitch name="Openswitch 2"] ops2

# Links
ops1:if01 -- ops2:if01
"""


ip_addr1 = "2001::1"
ip_addr2 = "2001::2"

sw1_router_id = "9.0.0.1"
sw2_router_id = "9.0.0.2"

as_num1 = "1"
as_num2 = "2"

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


def configure_route_map_set_ipv6(dut, routemap, nexthop):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "set ipv6 next-hop global " + nexthop
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def configure_route_map_match_ipv6(dut, routemap, nexthop):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "match ipv6 next-hop " + nexthop
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def configure_route_map_match_ipv6_deny(dut, routemap, nexthop):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " deny 20"
    cmd1 = "match ipv6 next-hop " + nexthop
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def verify_bgp_routes(dut, network, next_hop):
    dump = dut("show ipv6 bgp")
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
        # Assigning an IPv6 address on interface 1 of SW1
        step("Configuring IPv6 address on link 1 SW1")
        ctx.ipv6_address("%s/64" % ip_addr1)
        # Assigning an IPv4 address on interface 1 of SW1
        ctx.ip_address("%s/8" % (sw1_router_id))

    verify_turn_on_interfaces(switch1, [switch1.ports["if01"]])

    with switch2.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW2.
        step("Enabling interface1 on SW2")
        ctx.no_shutdown()
        # Assigning an IPv6 address on interface 1 of SW2
        step("Configuring IPv4 address on link 1 SW2")
        ctx.ipv6_address("%s/64" % ip_addr2)
        # Assigning an IPv4 address on interface 1 for link 1 SW2
        ctx.ip_address("%s/8" % (sw2_router_id))

    verify_turn_on_interfaces(switch2, [switch2.ports["if01"]])

    """
    For SW1 and SW2, configure bgp
    """

    step("Configuring router id on SW1")
    configure_router_id(step, switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "2ccd:1:1::/67")

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "5d5d:1:1::/69")

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "7d5d:1:1::/85")

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "9966:1:2::/85")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, as_num1, ip_addr2, as_num2)

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, as_num2, sw2_router_id)

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "3dcd:1:1::/64")

    step("Configuring neighbors on SW2")
    configure_neighbor(switch2, as_num2, ip_addr1, as_num1)


def verify_routemap_set_ipv6(step, switch1, switch2):
    step("\n########## Verifying route-map set ipv6 global##########\n")

    step("Configuring no router bgp")
    enternoroutercontext(switch1, as_num1)

    step("Configuring route-map on SW1")
    configure_route_map_set_ipv6(switch1, "BGP_OUT", "2001::3")

    step("Configuring router id on SW1")
    configure_router_id(step, switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "2ccd:1:1::/67")

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "5d5d:1:1::/69")

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "7d5d:1:1::/85")

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "9966:1:2::/85")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, as_num1, ip_addr2, as_num2)

    step("Configuring neighbor route-map on SW1")
    configure_neighbor_rmap_out(switch1, as_num1, ip_addr2, as_num2, "BGP_OUT")

    exitcontext(switch2)
    wait_for_route(switch2, "2ccd:1:1::", "2001::3")
    wait_for_route(switch2, "9966:1:2::", "2001::3")
    wait_for_route(switch2, "5d5d:1:1::", "2001::3")
    wait_for_route(switch2, "7d5d:1:1::", "2001::3")
    wait_for_route(switch2, "3dcd:1:1::", "::")

    dump = switch2("sh ipv6 bgp")

    set_ipv6_flag = False
    ipv6_nexthop_count = 0

    lines = dump.split("\n")
    for line in lines:
        if ("2ccd:1:1::" in line or "5d5d:1:1::" in line or
                "7d5d:1:1::" in line or "9966:1:2::" in line and
                "2001::3" in line):
            ipv6_nexthop_count += 1

    if ipv6_nexthop_count == 4:
        set_ipv6_flag = True

    assert set_ipv6_flag is True, "Failure to configure " \
        "\"set ipv6 nexthop global\""

    step("### \"set ipv6 nexthop global\" running succesfully ###\n")


def verify_routemap_match_ipv6(step, switch1, switch2):
    step("\n\n########## Verifying route-map match ipv6 ##########\n")

    step("Configuring no router bgp on SW2")
    enternoroutercontext(switch2, as_num2)

    step("Configuring route-map on SW2")
    configure_route_map_match_ipv6(switch2, "BGP_IN", "2001::3")

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, as_num2, sw2_router_id)

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "3dcd:1:1::/64")

    step("Configuring neighbors on SW2")
    configure_neighbor(switch2, as_num2, ip_addr1, as_num1)

    step("Configuring neighbor route-map on SW2")
    configure_neighbor_rmap_in(switch2, as_num2, ip_addr1, as_num1, "BGP_IN")

    exitcontext(switch2)
    wait_for_route(switch2, "2ccd:1:1::", "2001::3")
    wait_for_route(switch2, "9966:1:2::", "2001::3")
    wait_for_route(switch2, "5d5d:1:1::", "2001::3")
    wait_for_route(switch2, "7d5d:1:1::", "2001::3")
    wait_for_route(switch2, "3dcd:1:1::", "::")

    dump = switch2("sh ipv6 bgp")

    set_ipv6_flag = False
    ipv6_nexthop_count = 0

    lines = dump.split("\n")
    for line in lines:
        if "2ccd:1:1::" in line or "5d5d:1:1::" in line or \
           "7d5d:1:1::" in line or "9966:1:2::" in line and "2001::3" in line:
            ipv6_nexthop_count += 1

    if ipv6_nexthop_count == 4:
        set_ipv6_flag = True

    assert set_ipv6_flag is True, "Failure to configure " \
        "\"match ipv6 next-hop\""

    step("### \"match ipv6 next - hop\" running succesfully ###\n")


def verify_routemap_match_ipv6_1(step, switch1, switch2):
    step("\n\n########## Verifying route-map match ipv6 ##########\n")

    step("Configuring no router bgp on SW2")
    enternoroutercontext(switch2, as_num2)

    step("Configuring route-map on SW2")
    configure_no_route_map(switch2, "BGP_IN")

    step("Configuring route-map on SW2")
    configure_route_map_match_ipv6_deny(switch2, "BGP_IN", "2001::3")

    step("Configuring router id on SW2")
    configure_router_id(step, switch2, as_num2, sw2_router_id)

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "3dcd:1:1::/64")

    step("Configuring neighbors on SW2")
    configure_neighbor(switch2, as_num2, ip_addr1, as_num1)

    step("Configuring neighbor route-map on SW2")
    configure_neighbor_rmap_in(switch2, as_num2, ip_addr1, as_num1, "BGP_IN")

    exitcontext(switch2)
    dump = switch2("sh ipv6 bgp")

    set_ipv6_flag = False
    ipv6_nexthop_count = 0

    lines = dump.split("\n")
    for line in lines:
        if "2ccd:1:1::" in line or "5d5d:1:1::" in line or \
           "7d5d:1:1::" in line or "9966:1:2::" in line and "2001::3" in line:
            ipv6_nexthop_count += 1

    if ipv6_nexthop_count == 4:
        set_ipv6_flag = True

    assert set_ipv6_flag is False, "Failure to configure " \
        "\"match ipv6 next - hop\""

    step("### \"match ipv6 next - hop\" running succesfully ###\n")


@mark.timeout(600)
def test_bgp_ft_routemap_ipv6_next_hop(topology, step):
    ops1 = topology.get('ops1')
    ops2 = topology.get('ops2')

    assert ops1 is not None
    assert ops2 is not None

    ops1.name = "ops1"
    ops2.name = "ops2"

    configure(step, ops1, ops2)
    verify_routemap_set_ipv6(step, ops1, ops2)
    verify_routemap_match_ipv6(step, ops1, ops2)
    verify_routemap_match_ipv6_1(step, ops1, ops2)
