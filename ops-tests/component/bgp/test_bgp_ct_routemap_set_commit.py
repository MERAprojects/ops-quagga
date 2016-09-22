# -*- coding: utf-8 -*-

# (c) Copyright 2015 Hewlett Packard Enterprise Development LP
#
# GNU Zebra is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any
# later version.
#
# GNU Zebra is distributed in the hope that it will be useful, but
# WITHoutput ANY WARRANTY; withoutput even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Zebra; see the file COPYING.  If not, write to the Free
# Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.

from bgp_config import BgpConfig
from bgp_config import PrefixList
from bgp_routing import wait_for_route
from pytest import mark

# Topology definition. the topology contains two back to back switches
# having four links between them.
TOPOLOGY = """
# +-------+    +-------+
# |  sw1  <---->  sw2  |
# +-------+    +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2

# Links
sw1:if01 -- sw2:if01
"""

#
# This test checks the following commands:
#   * ip prefix-list <prefix-list-name> seq <seq-num> (permit|deny) <prefix>
#   * route map <route-map-name> permit seq_num
#   *   description <description>
#   *   match ip address prefix-list <prefix-list>
#   *   set as-path prepend >asn>
#   *   set origin (egp|igp|incomplete)
#   *   set ipv6 next-hop global X:X::X:X
#   * neighbor <neighbor-router-id> route-map <prefix-list> (in|out)
#
# Topology:
#   S1 [interface 1]<--->[interface 2] S2
#
# Configuration of BGP1:
# ----------------------------------------------------------------------------
# !
# router bgp 1
#  bgp router-id 8.0.0.1
#  network 9.0.0.0/8
#  neighbor 8.0.0.2 remote-as 2
#  neighbor 8.0.0.2 route-map BGP1_IN in
# !
# ip prefix-list BGP1_IN seq 5 deny 11.0.0.0/8
# ip prefix-list BGP1_IN seq 10 permit 10.0.0.0/8
# !
# route-map BGP1_IN permit 5
#  description A route-map description for testing.
#  match ip address prefix-list BGP1_IN
#  set origin egp
#  set extcommunity rt 2:0 4:0
#  set extcommunity soo 3:0 5:0
#  set ipv6 next-hop 2001:db8::0:1
#  set as-path prepend 1
# !
#
# Configuration of BGP2:
# ----------------------------------------------------------------------------
# !
# router bgp 2
#  bgp router-id 8.0.0.2
#  network 10.0.0.0/8
#  network 11.0.0.0/8
#  neighbor 8.0.0.1 remote-as 1
# !
#
# Expected routes of BGP1:
# ----------------------------------------------------------------------------
# BGP table version is 0, local router ID is 8.0.0.1
#    Network          Next Hop            Metric LocPrf Weight Path
# *> 9.0.0.0          0.0.0.0                  0         32768 i
# *> 10.0.0.0         8.0.0.2                  0             0 2 i
#
# Expected routes of BGP2:
# ----------------------------------------------------------------------------
# BGP table version is 0, local router ID is 8.0.0.2
# Origin codes: i - IGP, e - EGP, ? - incomplete
#
#    Network          Next Hop            Metric LocPrf Weight Path
# *> 9.0.0.0          8.0.0.1                  0             0 1 i
# *> 10.0.0.0         0.0.0.0                  0         32768 i
# *> 11.0.0.0         0.0.0.0                  0         32768 i


default_pl = "8"
default_netmask = "255.0.0.0"
rm_description = "A route-map description for testing."
extcommunity_rt_str = "2:0"
extcommunity_soo_str = "3:0"
extcommunity_rt_str2 = "4:0"
extcommunity_soo_str2 = "5:0"
ipv6_nexthop_gbl_addr = ipv6_nexthop_local_addr = "2001:db8::0:1"
bgp_configArr = []
all_cfg_array = []
switches = []
bgp_config1 = BgpConfig("1", "8.0.0.1", "9.0.0.0")
bgp_config2 = BgpConfig("2", "8.0.0.2", "10.0.0.0")


def configure_switches(step):
    step("Configuring switch IPs..")
    i = 0
    for switch in switches:
        bgp_cfg = bgp_configArr[i]
        # Configure the IPs between the switches
        switch("configure terminal")
        switch("interface {}".format(switch.ports["if01"]))
        switch("no shutdown")
        switch("ip address {}/{}".format(bgp_cfg.routerid, default_pl))
        switch("exit")
        i += 1


def setup_bgp_config(step, bgp_config1, bgp_config2):
    step("Setup of BGP configurations...")
    # Create BGP configurations
    # bgp_config1 = BgpConfig("1", "8.0.0.1", "9.0.0.0")
    # bgp_config2 = BgpConfig("2", "8.0.0.2", "10.0.0.0")
    # Add additional network for BGP2.
    bgp_config2.add_network("11.0.0.0")

    # Add the neighbors for each BGP config
    bgp_config1.add_neighbor(bgp_config2)
    bgp_config2.add_neighbor(bgp_config1)
    bgp_configArr.append(bgp_config1)
    bgp_configArr.append(bgp_config2)

    # Configure "deny" for "in" of the second network of BGP2
    neighbor = bgp_config1.neighbors[0]
    network = neighbor.networks[1]
    prefix_list = PrefixList("BGP{}_IN".format(bgp_config1.asn), 5, "deny",
                             network, default_pl)
    bgp_config1.prefix_lists.append(prefix_list)
    bgp_config1.add_route_map(neighbor, prefix_list, "in", "permit")

    # Configure so that the other route can be permitted
    network = neighbor.networks[0]
    prefix_list = PrefixList("BGP{}_IN".format(bgp_config1.asn), 10, "permit",
                             network, default_pl)
    bgp_config1.prefix_lists.append(prefix_list)


def apply_bgp_config(step):
    step("Applying BGP configurations...")
    i = 0
    for bgp_cfg in bgp_configArr:
        step("Applying configurations for BGP: {}".format(bgp_cfg.routerid))
        cfg_array = []

        # Add any prefix-lists
        add_prefix_list_configs(bgp_cfg, cfg_array)

        # Add route-map configs
        add_route_map_configs(bgp_cfg, cfg_array)
        for config in cfg_array:
            switches[i](config)
        del cfg_array[:]

        # Initiate BGP configuration
        cfg_array.append("router bgp {}".format(bgp_cfg.asn))
        cfg_array.append("bgp router-id {}".format(bgp_cfg.routerid))

        # Add the networks this bgp will be advertising
        for network in bgp_cfg.networks:
            cfg_array.append("network {}/{}".format(network, default_pl))

        # Add the neighbors of this switch
        for neighbor in bgp_cfg.neighbors:
            cfg_array.append("neighbor {} remote-as {}"
                             "".format(neighbor.routerid, neighbor.asn))

        # Add the neighbor route-maps configs
        add_neighbor_route_map_configs(bgp_cfg, cfg_array)
        for config in cfg_array:
            switches[i](config)
        switches[i]("exit")

        # Add the configuration arrays to an array so that it can be used
        # for verification later.
        all_cfg_array.append(cfg_array)
        i += 1


def add_route_map_configs(bgp_cfg, cfg_array):
    for route_map in bgp_cfg.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name, action,
                                                     prefix_list.seq_num))
        cfg_array.append("description {}".format(rm_description))
        cfg_array.append("match ip address prefix-list {}"
                         "".format(prefix_list.name))


def add_prefix_list_configs(bgp_cfg, cfg_array):
    # Add any prefix-lists
    for prefix_list in bgp_cfg.prefix_lists:
        cfg_array.append("ip prefix-list {} seq {} {} {}/{}"
                         "".format(prefix_list.name, prefix_list.seq_num,
                                   prefix_list.action, prefix_list.network,
                                   prefix_list.prefix_len))


def add_neighbor_route_map_configs(bgp_cfg, cfg_array):
    # Add the route-maps
    for route_map in bgp_cfg.route_maps:
        neighbor = route_map[0]
        prefix_list = route_map[1]
        dir = route_map[2]
        cfg_array.append("neighbor {} route-map {} {}"
                         "".format(neighbor.routerid, prefix_list.name, dir))


def verify_bgp_running(step):
    step("Verifying bgp processes..")
    for switch in switches:
        pid = switch("pgrep -f bgpd", shell='bash')
        pid = pid.strip()
        assert pid != "" and pid is not None


def verify_bgp_configs(step):
    step("Verifying all configurations..")
    i = 0
    for switch in switches:
        output = switch("do show running-config")
        bgp_cfg_array = all_cfg_array[i]
        for cfg in bgp_cfg_array:
            assert cfg in output
        i += 1


def verify_bgp_routes(step, bgp_config1):
    step("Verifying routes...")
    # For each bgp, verify that it is indeed advertising itself
    verify_advertised_routes(step)
    # For each switch, verify the number of routes received
    verify_routes_received(step, bgp_config1)


def verify_advertised_routes(step):
    step("Verifying advertised routes...")
    i = 0
    for bgp_cfg in bgp_configArr:
        switch = switches[i]
        next_hop = "0.0.0.0"
        for network in bgp_cfg.networks:
            wait_for_route(switch, next_hop, network)
        i += 1


def verify_routes_received(step, bgp_config1):
    step("Verifying routes received...")
    switch = switches[0]
    neighbor = bgp_config1.neighbors[0]
    next_hop = neighbor.routerid

    # First network of BGP2 should be permitted
    network = neighbor.networks[0]
    step("Network: {}, Next-hop: {} - Should exist..."
         "".format(network, next_hop))
    wait_for_route(switch, next_hop, network)

    # Second network of BGP2 should NOT be permitted
    network = neighbor.networks[1]
    step("Network: {}, Next-hop: {} - Should NOT exist..."
         "".format(network, next_hop))
    wait_for_route(switch, next_hop, network, exists=False)


def verify_routemap_set_as_path_prepend(step, bgp_config1):
    step("Verifying route-map set as-path prepend")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name,
                                                     action,
                                                     prefix_list.seq_num))
        cfg_str = "set as-path prepend {}".format(bgp_config1.asn)
        cfg_array.append(cfg_str)
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    switch("exit")
    output = switch("do show running-config")
    assert cfg_str in output


def verify_routemap_no_set_as_path_prepend(step, bgp_config1):
    step("Verifying route-map no set as-path prepend")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name,
                                                     action,
                                                     prefix_list.seq_num))
        cfg_str = "no set as-path prepend {}".format(bgp_config1.asn)
        cfg_array.append(cfg_str)
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    switch("exit")
    output = switch("do show running-config")
    assert cfg_str not in output


def verify_routemap_set_extcommunity_rt(step, bgp_config1):
    step("Verifying route-map set extcommunity rt ")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name,
                                                     action,
                                                     prefix_list.seq_num))
        cfg_str = "set extcommunity rt {} {}".format(extcommunity_rt_str,
                                                     extcommunity_rt_str2)
        cfg_array.append(cfg_str)
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    switch("exit")
    output = switch("do show running-config")
    assert cfg_str in output


def verify_routemap_no_set_extcommunity_rt(step, bgp_config1):
    step("Verifying route-map no set extcommunity rt ")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name, action,
                                                     prefix_list.seq_num))
        cfg_str = "no set extcommunity rt {} {}".format(extcommunity_rt_str,
                                                        extcommunity_rt_str2)
        cfg_array.append(cfg_str)
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    switch("exit")
    output = switch("do show running-config")
    assert cfg_str not in output


def verify_routemap_set_extcommunity_soo(step, bgp_config1):
    step("Verifying route-map set extcommunity soo ")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name, action,
                                                     prefix_list.seq_num))
        cfg_str = "set extcommunity soo {} {}".format(extcommunity_soo_str,
                                                      extcommunity_soo_str2)
        cfg_array.append(cfg_str)
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    output = switch("do show running-config")
    assert cfg_str in output


def verify_routemap_no_set_extcommunity_soo(step, bgp_config1):
    step("Verifying route-map no set extcommunity soo")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name, action,
                                                     prefix_list.seq_num))
        cfg_str = "set extcommunity soo {} {}".format(extcommunity_soo_str,
                                                      extcommunity_soo_str2)
        cfg_array.append("no {}".format(cfg_str))
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    switch("exit")
    output = switch("do show running-config")
    assert cfg_str not in output


def verify_routemap_set_ipv6_next_hop_global(step, bgp_config1):
    step("Verifying route-map set ipv6 next-hop global")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name, action,
                                                     prefix_list.seq_num))
        cfg_str = "set ipv6 next-hop global {}".format(ipv6_nexthop_gbl_addr)
        cfg_array.append(cfg_str)
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    switch("exit")
    output = switch("do show running-config")
    assert cfg_str in output


def verify_routemap_no_set_ipv6_next_hop_global(step, bgp_config1):
    step("Verifying route-map no set ipv6 next-hop global")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name, action,
                                                     prefix_list.seq_num))
        cfg_str = "set ipv6 next-hop global {}".format(ipv6_nexthop_gbl_addr)
        cfg_array.append("no {}".format(cfg_str))
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    switch("exit")
    output = switch("do show running-config")
    assert cfg_str not in output


def verify_routemap_set_origin(origin_type, step, bgp_config1):
    step("Verifying route-map set origin")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name, action,
                                                     prefix_list.seq_num))
        cfg_str = "set origin {}".format(str(origin_type))
        cfg_array.append(cfg_str)
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    switch("exit")
    output = switch("do show running-config")
    assert cfg_str in output


def verify_routemap_no_set_origin(origin_type, step, bgp_config1):
    step("Verifying route-map no set origin")
    cfg_array = []
    cfg_array.append("router bgp {}".format(bgp_config1.asn))
    for route_map in bgp_config1.route_maps:
        prefix_list = route_map[1]
        action = route_map[3]
        cfg_array.append("route-map {} {} {}".format(prefix_list.name, action,
                                                     prefix_list.seq_num))
        cfg_str = "no set origin {}".format(str(origin_type))
        cfg_array.append(cfg_str)
    switch = switches[0]
    for config in cfg_array:
        switch(config)
    switch("exit")
    output = switch("do show running-config")
    assert cfg_str not in output


def verify_no_routemap(step, bgp_config1):
    step("Verifying no route-map")
    switch = switches[0]
    route_map = bgp_config1.route_maps[0]
    prefix_list = route_map[1]
    action = route_map[3]
    step("Unconfiguring route-map")
    cfg = "route-map {} {} {}".format(prefix_list.name, action,
                                      prefix_list.seq_num)
    cmd = "no {}".format(cfg)
    switch(cmd)
    step("Checking route-map config")
    output = switch("do show running-config")
    assert cfg not in output


def verify_no_ip_prefix_list(step, bgp_config1):
    step("Verifying no ip prefix-list")
    switch = switches[0]
    for prefix_list in bgp_config1.prefix_lists:
        cfg = "ip prefix-list {} seq {} {} {}/{}" \
              "".format(prefix_list.name,
                        prefix_list.seq_num,
                        prefix_list.action,
                        prefix_list.network,
                        prefix_list.prefix_len)
        cmd = "no {}".format(cfg)
        step("Unconfiguring ip prefix-list {}".format(prefix_list.name))
        switch(cmd)
        step("Checking ip prefix-list config")
        output = switch("do show running-config")
        assert cfg not in output


@mark.gate
def test_bgp_ct_routemap_set_commit(topology, step):
    sw1 = topology.get("sw1")
    sw2 = topology.get("sw2")
    assert sw1 is not None
    assert sw2 is not None
    switches.append(sw1)
    switches.append(sw2)
    print(bgp_config1)
    setup_bgp_config(step, bgp_config1, bgp_config2)
    print(bgp_config1)
    configure_switches(step)
    verify_bgp_running(step)
    apply_bgp_config(step)
    # mininet_cli()
    verify_bgp_configs(step)
    verify_bgp_routes(step, bgp_config1)
    verify_routemap_set_as_path_prepend(step, bgp_config1)
    verify_routemap_no_set_as_path_prepend(step, bgp_config1)
    verify_routemap_set_extcommunity_rt(step, bgp_config1)
    verify_routemap_no_set_extcommunity_rt(step, bgp_config1)
    verify_routemap_set_extcommunity_soo(step, bgp_config1)
    verify_routemap_no_set_extcommunity_soo(step, bgp_config1)
    verify_routemap_set_ipv6_next_hop_global(step, bgp_config1)
    verify_routemap_no_set_ipv6_next_hop_global(step, bgp_config1)
    verify_routemap_set_origin('egp', step, bgp_config1)
    verify_routemap_no_set_origin('egp', step, bgp_config1)
    verify_routemap_set_origin('igp', step, bgp_config1)
    verify_routemap_no_set_origin('igp', step, bgp_config1)
    verify_routemap_set_origin('incomplete', step, bgp_config1)
    verify_routemap_no_set_origin('incomplete', step, bgp_config1)
    verify_no_routemap(step, bgp_config1)
    verify_no_ip_prefix_list(step, bgp_config1)
