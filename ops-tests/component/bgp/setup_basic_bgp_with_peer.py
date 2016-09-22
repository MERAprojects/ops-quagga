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


def test_setup_basic_bgp_with_peer(topology, step):
    sw1 = topology.get("sw1")
    sw2 = topology.get("sw2")
    switches = [sw1, sw2]
    bgp1_asn = "6001"
    bgp1_router_id = "9.0.0.1"
    bgp1_network = "11.0.0.0"
    bgp2_asn = "6002"
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
    bgp_configs = [bgp1_config, bgp2_config]
    step("1-Verifying bgp processes...")
    for switch in switches:
        pid = switch("pgrep -f bgpd", shell='bash')
        pid = pid.strip()
        assert pid != "" and pid is not None
    step("2-Configuring switch IPs...")
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
    step("3-Configuring bgp on all switches...")
    i = 0
    for switch in switches:
        configs = bgp_configs[i]
        i += 1
        for config in configs:
            switch(config)
