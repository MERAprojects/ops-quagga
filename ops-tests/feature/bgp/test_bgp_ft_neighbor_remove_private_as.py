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

from vtysh_utils import SwitchVtyshUtils
from interface_utils import verify_turn_on_interfaces

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


bgp1_asn = "1"
bgp1_router_id = "9.0.0.1"
bgp1_network = "11.0.0.0"

bgp2_asn = "2"
bgp2_router_id = "9.0.0.2"
bgp2_intf2 = "29.0.0.4"
bgp2_network = "12.0.0.0"

bgp3_asn = "65000"
bgp3_router_id = "29.0.0.3"
bgp3_network = "13.0.0.0"

bgp1_neighbor = bgp2_router_id
bgp1_neighbor_asn = bgp2_asn

bgp2_neighbor = bgp1_router_id
bgp2_neighbor_asn = bgp1_asn

bgp2_neighbor1 = bgp3_router_id
bgp2_neighbor_asn1 = bgp3_asn

bgp3_neighbor = bgp2_intf2
bgp3_neighbor_asn = bgp2_asn

bgp_network_pl = "8"
bgp_network_mask = "255.0.0.0"
bgp_router_ids = [bgp1_router_id, bgp2_router_id, bgp3_router_id]

bgp1_config = ["router bgp %s" % bgp1_asn,
               "bgp router-id %s" % bgp1_router_id,
               "network %s/%s" % (bgp1_network, bgp_network_pl),
               "neighbor %s remote-as %s" % (bgp1_neighbor, bgp1_neighbor_asn)]

bgp2_config = ["router bgp %s" % bgp2_asn,
               "bgp router-id %s" % bgp2_router_id,
               "network %s/%s" % (bgp2_network, bgp_network_pl),
               "neighbor %s remote-as %s" % (bgp2_neighbor, bgp2_neighbor_asn),
               "neighbor %s remote-as %s" % (bgp2_neighbor1,
                                             bgp2_neighbor_asn1),
               "neighbor %s remove-private-AS" % bgp2_neighbor]

bgp3_config = ["router bgp %s" % bgp3_asn,
               "bgp router-id %s" % bgp3_router_id,
               "network %s/%s" % (bgp3_network, bgp_network_pl),
               "neighbor %s remote-as %s" % (bgp3_neighbor, bgp3_neighbor_asn)]

bgp_configs = [bgp1_config, bgp2_config, bgp3_config]

num_of_switches = 3
num_hosts_per_switch = 0

switch_prefix = "s"

switches = []


def configure_switch_ips(step):
    step("\n########## Configuring switch IPs.. ##########\n")

    i = 0
    for switch in switches:
        # Configure the IPs between the switches
        switch("configure terminal")
        switch("interface %s" % switch.ports["if01"])
        switch("no shutdown")
        switch("ip address %s/%s" % (bgp_router_ids[i],
                                     bgp_network_pl))
        switch("end")
        if i == 1:
            switch("configure terminal")
            switch("interface %s" % switch.ports["if02"])
            switch("no shutdown")
            switch("ip address %s/%s" % (bgp2_intf2,
                                         bgp_network_pl))
            switch("end")

        i += 1

def verify_interface_on(step):
    step("\n########## Verifying interface are up ########## \n")

    for switch in switches:
        ports = [switch.ports["if01"]]
        verify_turn_on_interfaces(switch, ports)

    step("\nExiting verify_interface_on\n")


def verify_bgp_running(step):
    step("\n########## Verifying bgp processes.. ##########\n")

    for switch in switches:
        pid = switch("pgrep -f bgpd", shell="bash").strip()
        assert (pid != ""), "bgpd process not running on switch %s" % \
            switch.name

        step("### bgpd process exists on switch %s ###\n" % switch.name)


def configure_bgp(step):
    step("\n########## Configuring BGP on all switches.. ##########\n")

    i = num_of_switches - 1
    for iteration in range(num_of_switches):
        switch = switches[i]
        cfg_array = bgp_configs[i]
        i -= 1

        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)


def reconfigure_neighbor(step):
    step("### Reconfiguring neighbor to refresh routes ###\n")
    switch = switches[0]
    cfg_array = []
    cfg_array.append("router bgp %s" % bgp1_asn)
    cfg_array.append("no neighbor %s" % bgp1_neighbor)
    SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

    step("### Verifying route removed prior to proceeding ###\n")
    network = bgp3_network
    next_hop = bgp2_router_id
    route_should_exist = False
    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop,
                                            route_should_exist)

    assert not found, "Route %s -> %s still exists" % (network, next_hop)

    step("### Configuring neighbor again... ###\n")
    cfg_array = []
    cfg_array.append("router bgp %s" % bgp1_asn)
    cfg_array.append("neighbor %s remote-as %s" % (bgp1_neighbor,
                                                   bgp1_neighbor_asn))
    SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)


def unconfigure_remove_private_as(step):
    step("### Unconfiguring remove private AS for BGP2... ###\n")

    switch = switches[1]

    cfg_array = []
    cfg_array.append("router bgp %s" % bgp2_asn)
    cfg_array.append("no neighbor %s remove-private-AS" % bgp2_neighbor)

    SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)


def verify_route(step):
    step("### Verifying BGP route exists ###\n")

    switch = switches[0]
    found = SwitchVtyshUtils.wait_for_route(switch, bgp3_network,
                                            bgp2_router_id)
    assert found, "Route %s -> %s was not found" % (bgp3_network,
                                                    bgp2_router_id)


def check_remove_private_as(step, switch, network, next_hop, asn):
    step("### Checking remove private AS %s for %s -> %s ###\n" %
         (asn, network, next_hop))

    switch = switches[0]
    routes = switch("show ip bgp").split("\r\n")

    for rte in routes:
        if (network in rte) and (next_hop in rte) and (asn in rte):
            step("### ASN was found ###\n")
            return True

    step("### ASN was not found ###\n")
    return False


def verify_neighbor_remove_private_as(step):
    step("\n########## Verifying neighbor peer remove-private "
         "AS ##########\n")

    verify_route(step)

    step("### Peer's AS number should not be visible ###\n")

    switch = switches[0]
    network = bgp3_network
    next_hop = bgp2_router_id
    asn = bgp3_asn
    found = check_remove_private_as(step, switch, network, next_hop, asn)

    assert not found, "AS number %s is found on %s" % (asn, switch.name)

    step("### Verified AS number is not present ###\n")


def verify_no_neighbor_remove_private_as(step):
    step("\n########## Verifying no neighbor peer remove-private "
         "AS ##########\n")

    unconfigure_remove_private_as(step)
    reconfigure_neighbor(step)
    verify_route(step)

    step("### Peer's AS number should be visible ###\n")
    switch = switches[0]
    network = bgp3_network
    next_hop = bgp2_router_id
    asn = bgp3_asn

    found = check_remove_private_as(step, switch, network, next_hop, asn)
    assert found, "AS number %s is not found on %s" % (asn, switch.name)

    step("### Verified AS number is present ###\n")


def test_bgp_ft_neighbor_remove_private_as(topology, step):
    global switches
    ops1 = topology.get('ops1')
    ops2 = topology.get('ops2')
    ops3 = topology.get('ops3')

    assert ops1 is not None
    assert ops2 is not None
    assert ops3 is not None

    switches = [ops1, ops2, ops3]

    ops1.name = "ops1"
    ops2.name = "ops2"
    ops3.name = "ops3"

    configure_switch_ips(step)
    verify_interface_on(step)
    verify_bgp_running(step)
    configure_bgp(step)
    verify_neighbor_remove_private_as(step)
    verify_no_neighbor_remove_private_as(step)
