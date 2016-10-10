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

from bgp_config import BgpConfig
from vtysh_utils import SwitchVtyshUtils
from interface_utils import verify_turn_on_interfaces

TOPOLOGY = """
# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=openswitch name="Openswitch 2"] ops2
[type=openswitch name="Openswitch 3"] ops3

# Links
ops1:if01 -- ops2:if01
ops1:if02 -- ops3:if01
"""


num_of_switches = 3
num_hosts_per_switch = 0
switch_prefix = "s"

default_pl = "8"
default_netmask = "255.0.0.0"

switches = []
bgpconfigarr = []
bgp_config1 = []
bgp_config2 = []
bgp_config3 = []
all_cfg_array = []


def configure_switch_ips(step):
    step("\n########## Configuring switch IPs.. ##########\n")

    bgp_router_id = ['9.0.0.1', '9.0.0.2', '10.0.0.2']
    i = 0
    for switch in switches:

        if switch.name == "ops1":
            switch("configure terminal")
            switch("interface %s" % switch.ports["if02"])
            switch("no shutdown")
            switch("ip address 10.0.0.1/8")
            switch("end")

        # Configure the IPs between the switches
        switch("configure terminal")
        switch("interface %s" % switch.ports["if01"])
        switch("no shutdown")
        switch("ip address %s/%s" % (bgp_router_id[i],
                                     default_pl))
        switch("end")

        i += 1

def verify_interface_on(step):
    step("\n########## Verifying interface are up ########## \n")

    for switch in switches:
        int1 = switch.ports["if01"]
        if switch.name == "ops1":
            int2 = switch.ports["if02"]
            ports = [int1, int2]
        else:
            ports = [int1]
        verify_turn_on_interfaces(switch, ports)

def setup_bgp_config(step):
    global bgpconfigarr, bgp_config1, bgp_config2, bgp_config3
    step("\n########## Setup of BGP configurations... ##########\n")

    # Create BGP configurations
    bgp_config1 = BgpConfig("1", "9.0.0.1", "15.0.0.0")
    bgp_config2 = BgpConfig("2", "9.0.0.2", "12.0.0.0")
    bgp_config3 = BgpConfig("3", "10.0.0.2", "20.0.0.0")

    # Add the neighbors for each BGP config
    bgp_config1.add_neighbor(bgp_config2)
    bgp_config2.add_neighbor(bgp_config1)

    bgpconfigarr = [bgp_config1, bgp_config2, bgp_config3]


def apply_bgp_config(step):
    global all_cfg_array
    step("\n########## Applying BGP configurations... ##########\n")
    all_cfg_array = []

    i = 0
    for bgp_cfg in bgpconfigarr:
        step("### Applying configurations for BGP: %s ###\n" %
             bgp_cfg.routerid)
        cfg_array = []

        if i == 0:
            step("### Applying community list configurations for BGP1")
            cfg_array.append("ip community-list BGP_IN permit 2:0")
            cfg_array.append("ip community-list BGP_IN deny 3:0")
            step("### Applying route-map configurations for BGP1")
            cfg_array.append("route-map BGP_RMAP permit 10")
            cfg_array.append("match community BGP_IN")

        if i == 1:
            cfg_array.append("route-map BGP_2 permit 10")
            cfg_array.append("set community 2:0")

        if i == 2:
            cfg_array.append("route-map BGP_3 permit 10")
            cfg_array.append("set community 3:0")

        SwitchVtyshUtils.vtysh_cfg_cmd(switches[i], cfg_array)

        del cfg_array[:]

        # Initiate BGP configuration
        cfg_array.append("router bgp %s" % bgp_cfg.asn)
        cfg_array.append("bgp router-id %s" % bgp_cfg.routerid)

        # Add the networks this bgp will be advertising
        for network in bgp_cfg.networks:
            cfg_array.append("network %s/%s" % (network, default_pl))

        if i == 0:
            cfg_array.append("neighbor 10.0.0.2 remote-as 3")
            cfg_array.append("neighbor 10.0.0.2 route-map BGP_RMAP in")
            cfg_array.append("neighbor 9.0.0.2 remote-as 2")
            cfg_array.append("neighbor 9.0.0.2 route-map BGP_RMAP in")

        if i == 1:
            cfg_array.append("neighbor 9.0.0.1 remote-as 1")
            cfg_array.append("neighbor 9.0.0.1 route-map BGP_2 out")

        if i == 2:
            cfg_array.append("neighbor 10.0.0.1 remote-as 1")
            cfg_array.append("neighbor 10.0.0.1 route-map BGP_3 out")

        SwitchVtyshUtils.vtysh_cfg_cmd(switches[i], cfg_array)

        # Add the configuration arrays to an array so that it can be used
        # for verification later.
        all_cfg_array.append(cfg_array)

        i += 1


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

    switch = switches[0]

    # Network of BGP2 should be permitted by BGP1
    network = "12.0.0.0/8"
    next_hop = "9.0.0.2"

    step("### Verifying route for switch %s ###\n" % switch.name)
    step("### Network: %s, Next-hop: %s - Should exist... ###\n" %
         (network, next_hop))

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

    assert found, "Route %s -> %s exists on %s" % \
                  (network, next_hop, switch.name)

    # Network of BGP3 should NOT be permitted by BGP1
    network = "20.0.0.0/8"
    next_hop = "10.0.0.2"
    verify_route_exists = False

    step("### Verifying routes for switch %s ###\n" % switch.name)
    step("### Network: %s, Next-hop: %s - Should NOT exist... ###\n" %
         (network, next_hop))

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop,
                                            verify_route_exists)

    assert not found, "Route %s -> %s does not exist on %s" % \
                      (network, next_hop, switch.name)

    # Network of BGP1 should be permitted by BGP2
    switch = switches[1]
    network = "15.0.0.0/8"
    next_hop = "9.0.0.1"

    step("### Verifying route for switch %s ###\n" % switch.name)
    step("### Network: %s, Next-hop: %s - Should exist... ###\n" %
         (network, next_hop))

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

    assert found, "Route %s -> %s exists on %s" % \
                  (network, next_hop, switch.name)

    # Network of BGP1 should be permitted by BGP3
    switch = switches[2]
    network = "15.0.0.0/8"
    next_hop = "10.0.0.1"

    step("### Verifying route for switch %s ###\n" % switch.name)
    step("### Network: %s, Next-hop: %s - Should exist... ###\n" %
         (network, next_hop))

    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

    assert found, "Route %s -> %s exists on %s" % \
                  (network, next_hop, switch.name)


def verify_no_ip_community(step):
    step("\n########## Verifying no ip prefix-list ##########\n")
    switch = switches[0]

    cmd = "no ip community-list BGP_IN"

    step("### Unconfiguring ip community-list BGP_IN ###\n")
    SwitchVtyshUtils.vtysh_cfg_cmd(switch, [cmd])

    cfg = "ip community-list BGP_IN permit 2:0"
    step("### Checking ip community-list config ###\n")
    exists = SwitchVtyshUtils.verify_cfg_exist(switch, [])
    assert not exists, "Config \"%s\" was not removed" % cfg

    cfg = "ip community-list BGP_IN permit 3:0"
    step("### Checking ip community-list config ###\n")
    exists = SwitchVtyshUtils.verify_cfg_exist(switch, [])
    assert not exists, "Config \"%s\" was not removed" % cfg

    step("### ip community-list  configs were successfully removed ###\n")


def test_bgp_ft_ip_community_list(topology, step):
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
    setup_bgp_config(step)
    verify_bgp_running(step)
    apply_bgp_config(step)
    verify_bgp_configs(step)
    verify_bgp_routes(step)
    verify_no_ip_community(step)
