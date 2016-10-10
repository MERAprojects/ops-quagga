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
# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=openswitch name="Openswitch 2"] ops2
[type=host name="Host 1"] hs1
[type=host name="Host 2"] hs2

# Links
ops1:if01 -- ops2:if01
ops1:if02 -- hs1:if01
ops2:if02 -- hs2:if01
"""


bgp1_asn = "1"
bgp1_router_id = "9.0.0.1"
bgp1_network1 = "10.0.0.0"
bgp1_network2 = "11.0.0.0"
bgp1_network3 = "13.0.0.0"
bgp1_gateway = "11.0.1.254"
bgp1_prefix_list = "bgp%s_in" % bgp1_asn

bgp2_asn = "2"
bgp2_router_id = "9.0.0.2"
bgp2_network1 = "12.0.0.0"
bgp2_gateway = "12.0.1.254"
bgp2_prefix_list = "bgp%s_in" % bgp2_asn

bgp_gateways = [bgp1_gateway, bgp2_gateway]
bgp_gw_prefix = "24"
bgp_gw_netmask = "255.255.255.0"

bgp1_neighbor = bgp2_router_id
bgp1_neighbor_asn = bgp2_asn

bgp2_neighbor = bgp1_router_id
bgp2_neighbor_asn = bgp1_asn

bgp_network_pl = "8"
bgp_network_mask = "255.0.0.0"
bgp_router_ids = [bgp1_router_id, bgp2_router_id]

bgp_peer_group = "extern-peer-group"

bgp1_config = ["ip prefix-list %s seq 5 deny %s/%s" % (bgp1_prefix_list,
                                                       bgp1_network1,
                                                       bgp_network_pl),
               # permit the second network to be advertised
               "ip prefix-list %s seq 10 permit %s/%s" % (bgp1_prefix_list,
                                                          bgp1_network2,
                                                          bgp_network_pl),
               "route-map %s permit 5" % bgp1_prefix_list,
               "description bgp1 testing",
               "match ip address prefix-list %s" % bgp1_prefix_list,
               "router bgp %s" % bgp1_asn,
               "bgp router-id %s" % bgp1_router_id,
               "network %s/%s" % (bgp1_network1, bgp_network_pl),
               "network %s/%s" % (bgp1_network2, bgp_network_pl),
               "neighbor %s peer-group" % bgp_peer_group,
               "neighbor %s remote-as %s" % (bgp_peer_group,
                                             bgp1_neighbor_asn),
               "neighbor %s peer-group %s" % (bgp1_neighbor, bgp_peer_group),
               "neighbor %s route-map %s out" % (bgp1_neighbor,
                                                 bgp1_prefix_list)]

bgp2_config = ["ip prefix-list %s seq 5 deny %s/%s" % (bgp2_prefix_list,
                                                       bgp1_network3,
                                                       bgp_network_pl),
               # permit network 2 of bgp1 to be received
               "ip prefix-list %s seq 10 permit %s/%s" % (bgp2_prefix_list,
                                                          bgp1_network2,
                                                          bgp_network_pl),
               "route-map %s permit 5" % bgp2_prefix_list,
               "description bgp2 testing",
               "match ip address prefix-list %s" % bgp2_prefix_list,
               "router bgp %s" % bgp2_asn,
               "bgp router-id %s" % bgp2_router_id,
               "network %s/%s" % (bgp2_network1, bgp_network_pl),
               "neighbor %s peer-group" % bgp_peer_group,
               "neighbor %s remote-as %s" % (bgp_peer_group,
                                             bgp2_neighbor_asn),
               "neighbor %s peer-group %s" % (bgp2_neighbor, bgp_peer_group),
               "neighbor %s route-map %s in" % (bgp2_neighbor,
                                                bgp2_prefix_list)]

bgp_configs = [bgp1_config, bgp2_config]

# the host ips are in the same network as the routers
host1_ip_addr = "11.0.1.1"
host2_ip_addr = "12.0.1.1"
host_ip_addrs = ["%s/%s" % (host1_ip_addr, bgp_gw_netmask),
                 "%s/%s" % (host2_ip_addr, bgp_gw_netmask)]
host_networks = ["%s/%s" % (bgp2_network1, bgp_gw_netmask),
                 "%s/%s" % (bgp1_network2, bgp_gw_netmask)]

num_of_switches = 2
num_hosts = 2

switch_prefix = "s"
host_prefix = "h"

ping_attempts = 10

switches = []


def configure_switch_ips(step):
    step("\n########## Configuring switch IPs.. ##########\n")

    i = 0
    for switch in switches:
        # Configure the IPs of the interfaces
        # Configure the gateways for the switches
        switch("configure terminal")
        switch("interface %s" % switch.ports["if02"])
        switch("no shutdown")
        switch("ip address %s/%s" % (bgp_gateways[i],
                                     bgp_gw_prefix))
        switch("end")

        # Configure the IPs for the interfaces between the switches
        switch("configure terminal")
        switch("interface %s" % switch.ports["if01"])
        switch("no shutdown")
        switch("ip address %s/%s" % (bgp_router_ids[i],
                                     bgp_network_pl))
        switch("end")

        i += 1

    # Configure the IPs for the hosts
    i = 0
    for host in hosts:
        host.libs.ip.interface("if01", addr=host_ip_addrs[i], up=True)
        host("ip route add default via %s" % bgp_gateways[i])

        i += 1

def verify_interface_on(step):
    step("\n########## Verifying interface are up ########## \n")

    for switch in switches:
        ports = [switch.ports["if01"], switch.ports["if02"]]
        verify_turn_on_interfaces(switch, ports)

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
    step("\n########## Verifying routes... ##########\n")

    step("### Checking the following routes that SHOULD exist: ###\n")
    verify_bgp_route_exists(step,
                            switches[0],
                            bgp2_network1,
                            bgp2_router_id)

    verify_bgp_route_exists(step,
                            switches[1],
                            bgp1_network2,
                            bgp1_router_id)

    step("### Checking the following routes that SHOULD NOT exist ###\n")
    verify_bgp_route_doesnt_exists(step,
                                   switches[1],
                                   bgp1_network1,
                                   bgp1_router_id)

    verify_bgp_route_doesnt_exists(step,
                                   switches[1],
                                   bgp1_network3,
                                   bgp1_router_id)


def verify_configs(step):
    step("\n########## Verifying all configurations.. ##########\n")

    for i in range(0, len(bgp_configs)):
        bgp_cfg = bgp_configs[i]
        switch = switches[i]

        for cfg in bgp_cfg:
            res = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg])
            assert res, "Config \"%s\" was not correctly configured!" % cfg

    step("### All configurations were verified successfully ###\n")


def verify_bgp_route_exists(step, switch, network, next_hop):
    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

    assert found, "Could not find route (%s -> %s) on %s" % \
                  (network, next_hop, switch.name)


def verify_bgp_route_doesnt_exists(step, switch, network, next_hop):
    route_should_exist = False
    found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop,
                                            route_should_exist)

    assert not found, "Route should not exist (%s -> %s) on %s" % \
                      (network, next_hop, switch.name)


def get_ping_hosts_result(step):
    hs1 = hosts[0]
    hs2 = hosts[1]

    step("### Ping %s from %s ###\n" % (hs1.name, hs2.name))
    ping1 = hs1.libs.ping.ping(10, host2_ip_addr)
    ping2 = hs2.libs.ping.ping(10, host1_ip_addr)
    if ping1["received"] >= 7 and ping2["received"] >= 7:
        return True
    elif ping1["loss_pc"] == 10 and ping2["loss_pc"] == 10:
        return False


def verify_hosts_ping_ok(step):
    step("\n########## Verifying PING successful.. ##########\n")

    for i in range(ping_attempts):
        result = get_ping_hosts_result(step)
        if result:
            break

    assert result, "PING failed"

    step("### Pings successful ###\n")


def verify_hosts_ping_fail(step):
    step("\n########## Verifying PING Failure (negative case) ##########\n")

    result = get_ping_hosts_result(step)
    assert not result, "PING did not fail when it was supposed to."


def test_bgp_ft_routemaps_with_hosts_ping(topology, step):
    global switches, hosts
    ops1 = topology.get('ops1')
    ops2 = topology.get('ops2')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert ops1 is not None
    assert ops2 is not None
    assert hs1 is not None
    assert hs2 is not None

    switches = [ops1, ops2]
    hosts = [hs1, hs2]

    ops1.name = "ops1"
    ops2.name = "ops2"
    hs1.name = "hs1"
    hs2.name = "hs2"

    configure_switch_ips(step)
    verify_interface_on(step)
    verify_bgp_running(step)
    verify_hosts_ping_fail(step)
    configure_bgp(step)
    verify_configs(step)
    verify_bgp_routes(step)
    verify_hosts_ping_ok(step)
