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

from bgp_config import BgpConfig, PrefixList
from vtysh_utils import SwitchVtyshUtils
from pytest import mark

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


num_of_switches = 2
num_hosts_per_switch = 0
switch_prefix = "s"

default_pl = "8"
default_netmask = "255.0.0.0"

nbrprefixlists = []


def addnbrprefixlist(nbr, list_, dir_):
    nbrprefixlists.append([nbr, list_, dir_])

switches = []
bgpconfigarr = []
bgp_config1 = []
bgp_config2 = []
all_cfg_array = []


def configure_switch_ips(step):
    step("\n########## Configuring switch IPs.. ##########\n")

    i = 0
    for switch in switches:
        bgp_cfg = bgpconfigarr[i]

        step("### Setting IP %s/%s on switch %s ###\n" %
             (bgp_cfg.routerid, default_pl, switch.name))

        # Configure the IPs between the switches
        switch("configure terminal")
        switch("interface %s" % switch.ports["if01"])
        switch("no shutdown")
        switch("ip address %s/%s" % (bgp_cfg.routerid,
                                     default_pl))
        switch("end")

        i += 1


def setup_bgp_config(step):
    global bgpconfigarr, bgp_config1, bgp_config2
    step("\n########## Setup of BGP configurations... ##########\n")

    # Create BGP configurations
    bgp_config1 = BgpConfig("1", "8.0.0.1", "9.0.0.0")
    bgp_config2 = BgpConfig("2", "8.0.0.2", "11.0.0.0")

    # Add additional network for the BGPs.
    bgp_config1.add_network("10.0.0.0")

    # Add the neighbors for each BGP config
    bgp_config1.add_neighbor(bgp_config2)
    bgp_config2.add_neighbor(bgp_config1)

    bgpconfigarr = [bgp_config1, bgp_config2]

    # Configure "deny" for "out" of the first network of BGP1
    # neighbor = bgp_config1.neighbors[0]
    network = bgp_config1.networks[0]
    prefixlist = PrefixList("BGP%s_OUT" % bgp_config1.asn, 5, "deny",
                            network, default_pl)

    bgp_config1.prefixlists.append(prefixlist)

    # Configure so that the second route from BGP1 is permitted
    network = bgp_config1.networks[1]
    prefixlist = PrefixList("BGP%s_OUT" % bgp_config1.asn, 10,
                            "permit", network, default_pl)

    bgp_config1.prefixlists.append(prefixlist)

    # Configure neighbor with prefix-list
    addnbrprefixlist("8.0.0.2", "BGP%s_OUT" % (bgp_config1.asn), "out")


def apply_bgp_config(step):
    global all_cfg_array
    step("\n########## Applying BGP configurations... ##########\n")
    all_cfg_array = []

    i = 0
    for bgp_cfg in bgpconfigarr:
        step("### Applying configurations for BGP: %s ###\n" %
             bgp_cfg.routerid)
        cfg_array = []

        # Add any prefix-lists
        add_prefix_list_configs(bgp_cfg, cfg_array)
        print(cfg_array)

        SwitchVtyshUtils.vtysh_cfg_cmd(switches[i], cfg_array)

        del cfg_array[:]

        # Initiate BGP configuration
        cfg_array.append("router bgp %s" % bgp_cfg.asn)
        cfg_array.append("bgp router-id %s" % bgp_cfg.routerid)

        # Add the networks this bgp will be advertising
        for network in bgp_cfg.networks:
            cfg_array.append("network %s/%s" % (network, default_pl))

        # Add the neighbors of this switch
        for neighbor in bgp_cfg.neighbors:
            cfg_array.append("neighbor %s remote-as %s" %
                             (neighbor.routerid, neighbor.asn))

        if bgp_cfg.asn is "1":
            # Add the neighbor prefix-list configs
            add_neighbor_prefix_list_configs(step, cfg_array)

        SwitchVtyshUtils.vtysh_cfg_cmd(switches[i], cfg_array)

        print(cfg_array)

        # Add the configuration arrays to an array so that it can be used
        # for verification later.
        all_cfg_array.append(cfg_array)

        i += 1


def add_prefix_list_configs(bgp_cfg, cfg_array):
    # add any prefix-lists
    for prefixlist in bgp_cfg.prefixlists:
        cfg_array.append("ip prefix-list %s seq %d %s %s/%s" %
                         (prefixlist.name, prefixlist.seq_num,
                          prefixlist.action, prefixlist.network,
                          prefixlist.prefixlen))


def add_neighbor_prefix_list_configs(step, cfg_array):
    # Add the neighbor prefix-lists
    for prefixlist in nbrprefixlists:
        neighbor = prefixlist[0]
        listname = prefixlist[1]
        direction = prefixlist[2]

        cfg_array.append("neighbor %s prefix-list %s %s" %
                         (neighbor, listname, direction))


def remove_neighbor_prefix_list_configs(step, cfg_array):
    # Remove the neighbor prefix-lists
    for prefixlist in nbrprefixlists:
        neighbor = prefixlist[0]
        listname = prefixlist[1]
        direction = prefixlist[2]

        cfg_array.append("no neighbor %s prefix-list %s %s" %
                         (neighbor, listname, direction))


def verify_bgp_running(step):
    step("\n########## Verifying bgp processes.. ##########\n")

    for switch in switches:
        pid = switch("pgrep -f bgpd", shell="bash").strip()
        assert (pid != ""), "bgpd process not running on switch %s" % \
                            switch.name

        step("### bgpd process exists on switch %s ###\n" % switch.name)


def verify_bgp_configs(step):
    step("\n########## Verifying all configurations.. ##########\n")

    i = 0
    for switch in switches:
        bgp_cfg_array = all_cfg_array[i]

        for cfg in bgp_cfg_array:
            res = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg])
            assert res, "Config \"%s\" was not correctly configured!" % cfg

        i += 1

    step("### All configurations were verified successfully ###\n")


def verify_bgp_routes(step):
    step("\n########## Verifying routes... ##########\n")

    # For each bgp, verify that it is indeed advertising itself
    verify_advertised_routes(step)

    # For each switch, verify the number of routes received
    verify_routes_received(step)


def verify_advertised_routes(step):
    step("### Verifying advertised routes... ###\n")

    i = 0
    for bgp_cfg in bgpconfigarr:
        switch = switches[i]

        next_hop = "0.0.0.0"

        for network in bgp_cfg.networks:
            found = SwitchVtyshUtils.wait_for_route(switch, network,
                                                    next_hop)

            assert found, "Could not find route (%s -> %s) on %s" % \
                          (network, next_hop, switch.name)

        i += 1


def verify_routes_received(step):
    step("### Verifying routes received... ###\n")

    # Check route on switch 1
    switch = switches[0]
    neighbor = bgp_config1.neighbors[0]
    network = neighbor.networks[0]
    next_hop = neighbor.routerid

    step("### Verifying route for switch %s ###\n" % switch.name)
    step("### Network: %s, Next-hop: %s - Should exist... ###\n" %
         (network, next_hop))

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

    assert found, "Route %s -> %s does not exist on %s" \
                  % (network, next_hop, switch.name)

    # Check routes on switch 2
    switch = switches[1]
    neighbor = bgp_config2.neighbors[0]

    # Second network should exist
    network = neighbor.networks[1]
    next_hop = neighbor.routerid

    step("### Verifying routes for switch %s ###\n" % switch.name)
    step("### Network: %s, Next-hop: %s - Should exist... ###\n" %
         (network, next_hop))

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

    assert found, "Route %s -> %s does not exist on %s" \
                  % (network, next_hop, switch.name)

    # First network should not exist.
    network = neighbor.networks[0]
    route_should_exist = False

    step("### Network: %s, Next-hop: %s - Should NOT exist... ###\n" %
         (network, next_hop))

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop,
                                            route_should_exist)

    assert not found, "Route %s -> %s exists on %s" \
                      % (network, next_hop, switch.name)


def reconfigure_neighbor(step):
    step("### Reset connection from BGP2 via reconfiguring neighbor ###\n")
    switch = switches[1]
    neighbor = bgp_config2.neighbors[0]

    cfg_array = []
    cfg_array.append("router bgp %s" % bgp_config2.asn)
    cfg_array.append("no neighbor %s" % neighbor.routerid)

    SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

    step("### Waiting for route to be removed ###\n")
    network = neighbor.networks[1]
    next_hop = neighbor.routerid
    route_should_exist = False

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop,
                                            route_should_exist)

    assert not found, "Route %s -> %s exists on %s" \
                      % (network, next_hop, switch.name)

    step("### Reconfiguring neighbor (BGP1) on BGP2 ###\n")
    cfg_array = []
    cfg_array.append("router bgp %s" % bgp_config2.asn)
    cfg_array.append("neighbor %s remote-as %s" % (neighbor.routerid,
                                                   neighbor.asn))
    SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

    step("### Waiting for route to be received again ###\n")

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

    assert found, "Route %s -> %s was not found on %s" \
                  % (network, next_hop, switch.name)


@mark.gate
def test_bgp_ft_prefix_list(topology, step):
    global switches
    ops1 = topology.get('ops1')
    ops2 = topology.get('ops2')

    assert ops1 is not None
    assert ops2 is not None

    switches = [ops1, ops2]

    ops1.name = "ops1"
    ops2.name = "ops2"

    setup_bgp_config(step)
    configure_switch_ips(step)
    verify_bgp_running(step)
    apply_bgp_config(step)
    verify_bgp_configs(step)
    verify_bgp_routes(step)
