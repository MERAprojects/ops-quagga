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

ipv6_addr1 = "2001::1"
ipv6_addr2 = "2001::2"
default_pl = "64"
as_num1 = "1"
as_num2 = "2"
sw1_router_id = "8.0.0.1"
sw2_router_id = "8.0.0.2"
vtysh_cr = '\r\n'
route_max_wait_time = 300


def enterconfigshell(dut):
    dut("configure terminal")


def enterroutercontext(dut, as_num):
    enterconfigshell(dut)
    dut("router bgp %s" % as_num)


def exitcontext(dut):
    dut("end")


def configure_route_map(dut, routemap, prefix_list):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 10"
    dut(cmd)
    cmd = "match ipv6 address prefix-list " + prefix_list
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


def configure_prefix_list(dut, name, seq, action, prefix, ge, le):
    enterconfigshell(dut)

    if ge == 0 and le == 0:
        cmd = (
            "ipv6 prefix-list " + name + " seq " + seq + " " + action +
            " " + prefix
        )
    elif ge != 0 and le == 0:
        cmd = (
            "ipv6 prefix-list " + name + " seq " + seq + " " + action + " " +
            prefix + " ge " + str(ge)
        )
    elif ge == 0 and le != 0:
        cmd = (
            "ipv6 prefix-list " + name + " seq " + seq + " " + action + " " +
            prefix + " le " + str(le)
        )
    elif ge != 0 and le != 0:
        cmd = (
            "ipv6 prefix-list " + name + " seq " + seq + " " + action + " " +
            prefix + " ge " + str(ge)+" le "+str(le)
        )
    dut(cmd)
    exitcontext(dut)


def verify_prefix_list_config(dut, name, seq, action, prefix, ge, le):
    enterconfigshell(dut)

    if ge == 0 and le == 0:
        cmd = (
            "ipv6 prefix-list " + name + " seq " + seq + " " + action +
            " " + prefix
        )
    elif ge != 0 and le == 0:
        cmd = (
            "ipv6 prefix-list " + name + " seq " + seq + " " + action + " " +
            prefix + " ge " + str(ge)
        )
    elif ge == 0 and le != 0:
        cmd = (
            "ipv6 prefix-list " + name + " seq " + seq + " " + action + " " +
            prefix + " le " + str(le)
        )
    elif ge != 0 and le != 0:
        cmd = (
            "ipv6 prefix-list " + name + " seq " + seq + " " + action + " " +
            prefix + " ge " + str(ge)+" le "+str(le)
        )
    dut(cmd)
    exitcontext(dut)


def configure_neighbor_rmap(dut, as_num1, network, as_num2, routemap,
                            direction):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " route-map " + routemap + " in"
    dut(cmd)
    exitcontext(dut)


def verify_routes(step, name, dut, network, next_hop, attempt=1):
    step("Verifying route on switch %s [attempt #%d] - Network: %s, "
         "Next-Hop: %s " % (name, attempt, network, next_hop))

    routes = dut("show ipv6 bgp")
    routes = routes.split("\r\n")
    for rte in routes:
        if (network in rte) and (next_hop in rte):
            return True
    return False


def wait_for_route(step, name, dut, network, next_hop, route_exist):
    for i in range(route_max_wait_time):
        attempt = i + 1
        found = verify_routes(step, name, dut, network, next_hop, attempt)
        if found == route_exist:
            if route_exist:
                result = "Route was found"
            else:
                result = "Route was not found"

            step(result)
            return found

        sleep(1)

    step("Condition not met after %s seconds " % route_max_wait_time)
    return found


def verify_bgp_routes(step, name, dut, network, next_hop, route_exist):

    found = wait_for_route(step, name, dut, network, next_hop, route_exist)

    if route_exist is True:
        assert found, "Route %s -> %s exists on %s" % \
                      (network, next_hop, name)
    elif route_exist is False:
        assert not found, "Route %s -> %s does not exist on %s" % \
                          (network, next_hop, name)


def configure(step, switch1, switch2):
    """
     - Configure the IP address in SW1, SW2
     - Configure ipv6 prefix
     - Configure route-map
     - Create router bgp instance on SW1 and SW2
     - Configure the router id
     - Configure the network range
     - Configure the neighbor
     - Apply route-map to neighbor on SW1
    """

    with switch1.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW1.
        step("Enabling interface1 on SW1")
        ctx.no_shutdown()
        # Assigning an IPv6 address on interface 1 of SW1
        step("Configuring IPv6 address on link 1 SW1")
        ctx.ipv6_address("%s/%s" % (ipv6_addr1, default_pl))

    verify_turn_on_interfaces(switch1, [switch1.ports["if01"]])

    with switch2.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW2.
        step("Enabling interface1 on SW1")
        ctx.no_shutdown()
        # Assigning an IPv6 address on interface 1 of SW2
        step("Configuring IPv6 address on link 1 SW2")
        ctx.ipv6_address("%s/%s" % (ipv6_addr2, default_pl))

    verify_turn_on_interfaces(switch2, [switch2.ports["if01"]])

    # Configuring ipv6 prefix-list on switch 1
    step("Configuring ipv6 prefix configuration on SW1")
    configure_prefix_list(switch1, "BGP1_IN", "10", "deny",
                          "9966:1:2::/64", 80, 100)

    configure_prefix_list(switch1, "BGP1_IN", "20", "permit",
                          "7d5d:1:1::/64", 0, 70)

    configure_prefix_list(switch1, "BGP1_IN", "30", "permit",
                          "5d5d:1:1::/64", 0, 70)

    configure_prefix_list(switch1, "BGP1_IN", "40", "permit",
                          "2ccd:1:1::/64", 65, 0)

    configure_prefix_list(switch1, "BGP1_IN", "50", "permit",
                          "4ddc:1:1::/64", 0, 0)

    # Configuring Route-map on switch 1
    step("Configuring route-map on SW1")
    configure_route_map(switch1, "BGP1_IN", "BGP1_IN")

    # Configuring BGP on switch 1
    step("Configuring router-id on SW1")
    configure_router_id(step, switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "3dcd:1:1::/64")

    step("Configuring bgp neighbor on SW1")
    configure_neighbor(switch1, as_num1, ipv6_addr2, as_num2)

    step("Applying route-map to bgp neighbor on SW1")
    configure_neighbor_rmap(switch1, as_num1, ipv6_addr2, as_num2,
                            "BGP1_IN", "in")
    sleep(5)

    # Configuring ipv6 prefix-list on switch 2
    step("Configuring ipv6 prefix list configuration on SW2")
    configure_prefix_list(switch2, "A_sample_name_to_verify_the_"
                          "max_length_of_the_prefix_list_name_that_"
                          "can_be_confd", "4294967295", "permit",
                          "any", 0, 0)

    step("Configuring ipv6 prefix list configuration on SW2")
    configure_prefix_list(switch2, "p2", "5", "deny", "any", 0, 0)

    # Boundary and limit testing and Negative testing for prefix list
    step("Boundary and limit testing and Negative testing for"
         " ipv6 prefix list configuration on SW2")

    verify_prefix_list_config(switch2, "p2", "0", "deny",
                              "any", 0, 0)

    verify_prefix_list_config(switch2, "p2", "4294967296", "deny",
                              "any", 0, 0)

    verify_prefix_list_config(switch2, "p2", "-429", "deny",
                              "any", 0, 0)

    # Configuring Route-map on switch 2
    step("Configuring route-map on SW2")
    configure_route_map(switch2, "BGP2_Rmap1", "A_sample_name_to_verify_the_"
                        "max_length_of_the_prefix_list_name_that_"
                        "can_be_confd")

    step("Configuring route-map on SW2")
    configure_route_map(switch2, "BGP2_Rmap2", "p2")

    # Configuring BGP on switch 2
    step("Configuring router-id on SW2")
    configure_router_id(step, switch2, as_num2, sw2_router_id)

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "2ccd:1:1::/67")

    configure_network(switch2, as_num2, "7d5d:1:1::/85")

    configure_network(switch2, as_num2, "5d5d:1:1::/69")

    configure_network(switch2, as_num2, "9966:1:2::/85")

    configure_network(switch2, as_num2, "4ddc:1:1::/64")

    configure_neighbor(switch2, as_num2, ipv6_addr1, as_num1)

    step("Applying route-map to bgp neighbor on SW2")
    configure_neighbor_rmap(switch2, as_num2, ipv6_addr1, as_num1,
                            "BGP2_Rmap1", "out")

    step("Applying route-map to bgp neighbor on SW2")
    configure_neighbor_rmap(switch2, as_num2, ipv6_addr1, as_num1,
                            "BGP2_Rmap2", "in")
    sleep(10)


def test_bgp_ft_ipv6_prefixlist(topology, step):
    ops1 = topology.get('ops1')
    ops2 = topology.get('ops2')

    assert ops1 is not None
    assert ops2 is not None

    ops1.name = "ops1"
    ops2.name = "ops2"

    configure(step, ops1, ops2)

    print("##### Verifying routes #####")

    step("Network 3dcd:1:1::/64 , Next-Hop ::"
         " should exist in ops1")
    verify_bgp_routes(step, ops1.name, ops1, "3dcd:1:1::/64", "::",
                      route_exist=True)

    step("Network 2ccd:1:1::/67 , Next-Hop %s"
         " should exist in ops1" % ipv6_addr2)
    verify_bgp_routes(step, ops1.name, ops1, "2ccd:1:1::/67", ipv6_addr2,
                      route_exist=True)

    step("Network 4ddc:1:1::/64 , Next-Hop  %s"
         " should exist in ops1" % ipv6_addr2)
    verify_bgp_routes(step, ops1.name, ops1, "4ddc:1:1::/64", ipv6_addr2,
                      route_exist=True)

    step("Network 5d5d:1:1::/69 , Next-Hop  %s"
         " should exist in ops1" % ipv6_addr2)
    verify_bgp_routes(step, ops1.name, ops1, "5d5d:1:1::/69", ipv6_addr2,
                      route_exist=True)

    step("Network 9966:1:2::/85 , Next-Hop  %s"
         " should not exist in ops1" % ipv6_addr2)
    verify_bgp_routes(step, ops1.name, ops1, "9966:1:2::/85", ipv6_addr2,
                      route_exist=False)

    step("Network 7d5d:1:1::/85 , Next-Hop  %s"
         " should not exist in ops1" % ipv6_addr2)
    verify_bgp_routes(step, ops1.name, ops1, "7d5d:1:1::/85", ipv6_addr2,
                      route_exist=False)

    step("Network 2ccd:1:1::/67 , Next-Hop ::"
         " should exist in ops2")
    verify_bgp_routes(step, ops2.name, ops2, "2ccd:1:1::/67", "::",
                      route_exist=True)

    step("Network 4ddc:1:1::/64 , Next-Hop ::"
         " should exist in ops2")
    verify_bgp_routes(step, ops2.name, ops2, "4ddc:1:1::/64", "::",
                      route_exist=True)

    step("Network 5d5d:1:1::/69 , Next-Hop ::"
         " should exist in ops2")
    verify_bgp_routes(step, ops2.name, ops2, "5d5d:1:1::/69", "::",
                      route_exist=True)

    step("Network 7d5d:1:1::/85 , Next-Hop ::"
         " should exist in ops2")
    verify_bgp_routes(step, ops2.name, ops2, "7d5d:1:1::/85", "::",
                      route_exist=True)

    step("Network  9966:1:2::/85 , Next-Hop ::"
         " should exist in ops2")
    verify_bgp_routes(step, ops2.name, ops2, " 9966:1:2::/85", "::",
                      route_exist=True)

    step("Network 3dcd:1:1::/64, Next-Hop %s"
         " should not exist in ops2" % ipv6_addr1)
    verify_bgp_routes(step, ops2.name, ops2, "3dcd:1:1::/64", ipv6_addr1,
                      route_exist=False)
