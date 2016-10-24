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

from bgp_config import BgpConfig, PrefixList
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


num_of_switches = 2
num_hosts_per_switch = 0
switch_prefix = "s"

default_pl = "8"
default_netmask = "255.0.0.0"
rm_metric = "1000"
rm_community = "1:5003"

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

def verify_interface_on(step):
    step("\n########## Verifying interface are up ########## \n")

    for switch in switches:
        ports = [switch.ports["if01"]]
        verify_turn_on_interfaces(switch, ports)

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
    neighbor = bgp_config1.neighbors[0]
    network = bgp_config1.networks[0]
    prefixlist = PrefixList("BGP%s_OUT" % bgp_config1.asn, 5, "deny",
                            network, default_pl)

    bgp_config1.prefixlists.append(prefixlist)
    bgp_config1.add_route_map(neighbor, prefixlist, "out",
                              "permit", rm_metric, rm_community)

    # Configure so that the second route from BGP1 is permitted
    network = bgp_config1.networks[1]
    prefixlist = PrefixList("BGP%s_OUT" % bgp_config1.asn, 10,
                            "permit", network, default_pl)

    bgp_config1.prefixlists.append(prefixlist)


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
        add_prefix_list_configs(step, bgp_cfg, cfg_array)

        # Add route-map configs
        add_route_map_configs(step, bgp_cfg, cfg_array)

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

        # Add the neighbor route-maps configs
        add_neighbor_route_map_configs(step, bgp_cfg, cfg_array)

        SwitchVtyshUtils.vtysh_cfg_cmd(switches[i], cfg_array)

        # Add the configuration arrays to an array so that it can be used
        # for verification later.
        all_cfg_array.append(cfg_array)

        i += 1


def add_route_map_configs(step, bgp_cfg, cfg_array):
    for routemap in bgp_cfg.routemaps:
        prefixlist = routemap[1]
        action = routemap[3]
        metric = routemap[4]
        community = routemap[5]

        cfg_array.append("route-map %s %s %d" %
                         (prefixlist.name, action,
                          prefixlist.seq_num))

        cfg_array.append("match ip address prefix-list %s" %
                         prefixlist.name)

        if metric != "":
            cfg_array.append("set metric %s" % metric)

        if community != "":
            cfg_array.append("set community %s additive" % community)


def add_prefix_list_configs(step, bgp_cfg, cfg_array):
    # Add any prefix-lists
    for prefixlist in bgp_cfg.prefixlists:
        cfg_array.append("ip prefix-list %s seq %d %s %s/%s" %
                         (prefixlist.name, prefixlist.seq_num,
                          prefixlist.action, prefixlist.network,
                          prefixlist.prefixlen))


def add_neighbor_route_map_configs(step, bgp_cfg, cfg_array):
    # Add the route-maps
    for routemap in bgp_cfg.routemaps:
        neighbor = routemap[0]
        prefixlist = routemap[1]
        dir = routemap[2]

        cfg_array.append("neighbor %s route-map %s %s" %
                         (neighbor.routerid, prefixlist.name, dir))


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

    # For each bgp, verify that it is indeed advertising itstep
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


def verify_metric_value(step):
    step("\n########## Verifying set metrics ##########\n")

    # Verify metric for the expected route
    switch = switches[1]

    # Network 2 of BGP1 is the permitted route
    network = bgp_config1.networks[1]
    next_hop = bgp_config1.routerid
    routemap = bgp_config1.routemaps[0]
    metric = routemap[4]

    matching = False

    cmd = "show ip bgp"
    routes = switch(cmd).split("\r\n")

    for rte in routes:
        if (network in rte) and (next_hop in rte) and (metric in rte):
            matching = True
            break

    assert matching, "Metric not matching for %s" % switch.name

    step("### Metric was found in route ###\n")


def verify_community_value(step):
    step("\n########## Verifying community value ##########\n")

    switch = switches[1]

    network = bgp_config1.networks[1]
    routemap = bgp_config1.routemaps[0]
    community = routemap[5]

    cmd = "show ip bgp %s" % network
    network_info = switch(cmd)

    assert rm_community in network_info, "Community value not matching"

    step("### Community value %s matching for network %s ###\n" %
         (community, network))


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


def verify_no_set_metric_and_community_values(step):
    step("\n########## Verifying no community and no "
         "set metric values ##########\n")

    step("### Setting no set metric and no community on BGP1 ###\n")
    switch = switches[0]
    # Network 2 of BGP1 is the permitted route
    network = bgp_config1.networks[1]
    next_hop = bgp_config1.routerid
    routemap = bgp_config1.routemaps[0]
    prefixlist = routemap[1]
    action = routemap[3]
    metric = routemap[4]

    cfg_array = []
    cfg_array.append("route-map %s %s %d" %
                     (prefixlist.name, action,
                      prefixlist.seq_num))
    cfg_array.append("no set metric")
    cfg_array.append("no set community")

    SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

    reconfigure_neighbor(step)

    step("### Verifying no set metric. Metric should not exist ###\n")
    switch = switches[1]
    cmd = "show ip bgp"
    routes = switch(cmd).split("\r\n")

    metric_found = False
    for rte in routes:
        if (network in rte) and (next_hop in rte) and (metric in rte):
            metric_found = True
            break

    assert not metric_found, "Metric was found"

    step("### Metric was successfully unset on BGP1 ###\n")
    step("### Verifying no set community ###\n")

    cmd = "sh ip bgp %s" % network
    network_info = switch(cmd)

    assert rm_community not in network_info, "Community should not be set"

    step("### Community value was successfully unset ###\n")


def verify_no_route_map_match(step):
    step("\n########## Verifying no route-map match ##########\n")
    step("### Removing route-map configuration ###\n")
    switch = switches[0]
    routemap = bgp_config1.routemaps[0]
    prefixlist = routemap[1]
    action = routemap[3]

    cfg_array = []
    cfg_array.append("route-map %s %s %d" %
                     (prefixlist.name, action,
                      prefixlist.seq_num))
    cfg_array.append("no match ip address prefix-list %s" %
                     prefixlist.name)

    SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

    reconfigure_neighbor(step)

    step("### Verifying first network of BGP1 received on BGP2 ###\n")
    switch = switches[1]
    network = bgp_config1.networks[0]
    next_hop = bgp_config1.routerid

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

    assert found, "Route %s -> %s was not found on %s" % \
                  (network, next_hop, switch.name)

    step("### Previously denied network is now present in BGP2 ###\n")


def test_bgp_ft_routemap(topology, step):
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
    verify_interface_on(step)
    verify_bgp_running(step)
    apply_bgp_config(step)
    verify_bgp_configs(step)
    verify_bgp_routes(step)
    verify_metric_value(step)
    # Disable community value checking until feature is implemented.
    # verify_community_value(step)
    verify_no_set_metric_and_community_values(step)
    verify_no_route_map_match(step)
