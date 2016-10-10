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

from vtysh_utils import SwitchVtyshUtils
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


bgp1_asn = "1"
bgp1_router_id = "9.0.0.1"
bgp1_network = "11.0.0.0"

bgp2_asn = "2"
bgp2_router_id = "9.0.0.2"
bgp2_network = "12.0.0.0"

bgp1_neighbor = bgp2_router_id
bgp1_neighbor_asn = bgp2_asn

bgp2_neighbor = bgp1_router_id
bgp2_neighbor_asn = bgp1_asn

bgp_network_pl = "8"
bgp_network_mask = "255.0.0.0"
bgp_router_ids = [bgp1_router_id, bgp2_router_id]

switches = []

bgp1_config = ["router bgp %s" % bgp1_asn,
               "bgp router-id %s" % bgp1_router_id,
               "network %s/%s" % (bgp1_network, bgp_network_pl),
               "neighbor %s remote-as %s" % (bgp1_neighbor, bgp1_neighbor_asn)]

bgp2_config = ["router bgp %s" % bgp2_asn,
               "bgp router-id %s" % bgp2_router_id,
               "network %s/%s" % (bgp2_network, bgp_network_pl),
               "neighbor %s remote-as %s" % (bgp2_neighbor, bgp2_neighbor_asn)]

bgp_configs = [bgp1_config, bgp2_config]

num_of_switches = 2
num_hosts_per_switch = 0

switch_prefix = "s"


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
    step("\n########## Applying BGP configurations... ##########\n")

    i = 0
    for switch in switches:
        step("### Applying BGP config on switch %s ###\n" % switch.name)
        cfg_array = bgp_configs[i]
        i += 1

        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)


def verify_bgp_routes(step):
    step("\n########## Verifying bgp routes.. ##########\n")

    verify_bgp_route(step, switches[0], bgp2_network,
                     bgp2_router_id)
    verify_bgp_route(step, switches[1], bgp1_network,
                     bgp1_router_id)


def verify_configs(step):
    step("\n########## Verifying all configurations.. ##########\n")

    for i in range(0, len(bgp_configs)):
        bgp_cfg = bgp_configs[i]
        switch = switches[i]

        for cfg in bgp_cfg:
            res = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg])
            assert res, "Config \"%s\" was not correctly configured!" % cfg


def verify_bgp_route(step, switch, network, next_hop):
    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

    assert found, "Could not find route (%s -> %s) on %s" % \
                  (network, next_hop, switch.name)


def test_bgp_ft_basic_bgp_route_advertise(topology, step):
    global switches

    ops1 = topology.get('ops1')
    ops2 = topology.get('ops2')

    assert ops1 is not None
    assert ops2 is not None

    switches = [ops1, ops2]

    ops1.name = "ops1"
    ops2.name = "ops2"

    configure_switch_ips(step)
    verify_interface_on(step)
    verify_bgp_running(step)
    configure_bgp(step)
    verify_configs(step)
    verify_bgp_routes(step)
