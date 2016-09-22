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

from pytest import mark

TOPOLOGY = """
# +-------+
# |       |     +-------+
# |  hsw1  <----->  sw1  |
# |       |     +-------+
# +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=host name="Host 1"] hsw1

# Links
hsw1:if01 -- sw1:if01
"""


@mark.gate
def test_bgp_ct_show_running_config(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    bgp1_asn = "12"
    bgp1_router_id = "9.0.0.1"
    bgp1_network = "11.0.0.0"
    bgp2_asn = "2"
    bgp2_router_id = "9.0.0.2"

    # bgp2_network = "12.0.0.0"
    bgp1_neighbor = bgp2_router_id
    bgp1_neighbor_asn = bgp2_asn
    bgp_network_pl = "8"

    #  bgp_network_mask = "255.0.0.0"
    paths = "20"
    description = "abcd"
    password = "abcdef"
    keepalive = "3"
    hold = "10"
    allow_as_in_number = "7"
    peer_group_name = "openswitch"
    bgp_config = ["router bgp {}".format(bgp1_asn),
                  "bgp router-id {}".format(bgp1_router_id),
                  "network {}/{}".format(bgp1_network, bgp_network_pl),
                  "maximum-paths {}".format(paths),
                  "timers bgp {} {}".format(keepalive, hold),
                  "neighbor {} remote-as {}".format(bgp1_neighbor,
                                                    bgp1_neighbor_asn),
                  "neighbor {} description {}".format(bgp1_neighbor,
                                                      description),
                  "neighbor {} password {}".format(bgp1_neighbor, password),
                  "neighbor {} timers {} {}".format(bgp1_neighbor, keepalive,
                                                    hold),
                  "neighbor {} allowas-in {}".format(bgp1_neighbor,
                                                     allow_as_in_number),
                  "neighbor {} remove-private-AS".format(bgp1_neighbor),
                  "neighbor {} peer-group".format(peer_group_name),
                  "neighbor {} peer-group {}".format(bgp1_neighbor,
                                                     peer_group_name),
                  "neighbor {} soft-reconfiguration"
                  " inbound".format(bgp1_neighbor)]
    step("1-Verifying bgp processes...")
    pid = sw1("pgrep -f bgpd", shell='bash')
    pid = pid.strip()
    assert pid != "" and pid is not None
    step("2-Applying BGP configurations...")
    sw1("configure terminal")
    for config in bgp_config:
        sw1(config)
    """
    sw1("router bgp {}".format(bgp1_asn))
    sw1("bgp router-id {}".format(bgp1_router_id))
    sw1("network {}/{}".format(bgp1_network, bgp_network_pl))
    sw1("maximum-paths {}".format(paths))
    sw1("timers bgp {} {}".format(keepalive, hold))
    sw1("neighbor {} remote-as {}".format(bgp1_neighbor, bgp1_neighbor_asn))
    sw1("neighbor {} description {}".format(bgp1_neighbor, description))
    sw1("neighbor {} password {}".format(bgp1_neighbor, password))
    sw1("neighbor {} timers {} {}".format(bgp1_neighbor, keepalive, hold))
    sw1("neighbor {} allowas-in {}".format(bgp1_neighbor, allow_as_in_number))
    sw1("neighbor {} remove-private-AS".format(bgp1_neighbor))
    sw1("neighbor {} peer-group".format(peer_group_name))
    sw1("neighbor {} peer-group {}".format(bgp1_neighbor, peer_group_name))
    sw1("neighbor {} soft-reconfiguration inbound".format(bgp1_neighbor))
    """
    output = sw1("do show running-config")
    for config in bgp_config:
        assert config in output
