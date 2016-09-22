# -*- coding: utf-8 -*-

# (c) Copyright 2015 Hewlett Packard Enterprise Development LP
#
# GNU Zebra is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any
# later version.
#
# GNU Zebra is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Zebra; see the file COPYING.  If not, write to the Free
# Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.

from bgp_routing import wait_for_route
from pytest import mark

TOPOLOGY = """
# +-------+      +-------+
# |  sw1  <------>  sw2  |
# +-------+      +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2

# Links
sw1:if01 -- sw2:if01
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
bgp_router_ids = [bgp1_router_id, bgp2_router_id]
bgp1_config = ["router bgp {}".format(bgp1_asn),
               "bgp router-id {}".format(bgp1_router_id),
               "network {}/{}".format(bgp1_network, bgp_network_pl),
               "neighbor {} remote-as {}".format(bgp1_neighbor,
                                                 bgp1_neighbor_asn)]
bgp2_config = ["router bgp {}".format(bgp2_asn),
               "bgp router-id {}".format(bgp2_router_id),
               "network {}/{}".format(bgp2_network, bgp_network_pl),
               "neighbor {} remote-as {}".format(bgp2_neighbor,
                                                 bgp2_neighbor_asn)]


def process_verification(switches, step):
    step("2-Verifying bgp processes...")
    for switch in switches:
        pid = switch("pgrep -f bgpd", shell='bash')
        pid = pid.strip()
        assert pid != "" and pid is not None


@mark.gate
def test_bgp_ct_show_ip_bgp(topology, step):  # noqa
    sw1 = topology.get("sw1")
    sw2 = topology.get("sw2")
    switches = [sw1, sw2]
    bgp_configs = [bgp1_config, bgp2_config]
    step("1-Configuring switch IPs...")
    i = 0
    for switch in switches:
        # Configure the IPs between the switches
        switch("configure terminal")
        switch("interface 1")
        switch("no shutdown")
        switch("ip address {}/{}".format(bgp_router_ids[i],
                                         bgp_network_pl))
        switch("exit")
        i += 1
    process_verification(switches, step)
    step("3-Configuring bgp on all switches...")
    i = 0
    for switch in switches:
        configs = bgp_configs[i]
        i += 1
        for config in configs:
            switch(config)
    step("4-Verifying all configurations...")
    i = 0
    for switch in switches:
        configs = bgp_configs[i]
        output = switch("do show running-config")
        for config in configs:
            assert config in output
        i += 1
    step("5-Verifying routes...")
    next_hop = bgp2_router_id
    network = bgp2_network
    wait_for_route(sw1, next_hop, network)
    next_hop = bgp1_router_id
    network = bgp1_network
    wait_for_route(sw2, next_hop, network)
    step("6-Verifying show ip bgp route (Negative Testing)")
    network = "1.1.1.0"
    output = sw1("do show ip bgp {}".format(network))
    assert "Network not in table" in output
    step("7-Verifying show ip bgp route (Positive Testing)")
    network = bgp2_network
    next_hop = bgp2_router_id
    wait_for_route(sw1, next_hop, network)
    step("8-Unconfiguring BGP network")
    sw1("router bgp {}".format(bgp1_asn))
    sw1("no neighbor {}".format(bgp1_neighbor))
    sw1("exit")
    step("9-Verifying route from BGP1 removed...")
    network = bgp1_network
    next_hop = bgp1_router_id
    wait_for_route(sw2, next_hop, network, exists=False)
    output = sw2("do show ip bgp {}".format(network))
    lines = output.split("\n")
    route_exists = False
    for line in lines:
        if next_hop in line:
            route_exists = True
            break
    assert not route_exists
