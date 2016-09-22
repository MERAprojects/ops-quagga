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


def test_bgp_ct_show_bgp_neighbors(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    bgp_router_asn = "1"
    bgp_neighbor_ipaddr = "1.1.1.1"
    bgp_neighbor_remote_as = "1111"

    # bgp_neighbor_config = ["router bgp %s" % bgp_router_asn,
    # "neighbor %s remote-as %s" % (bgp_neighbor_ipaddr,
    #                               bgp_neighbor_remote_as)]
    # no_bgp_neighbor_config = ["router bgp %s" % bgp_router_asn,
    #                     "no neighbor %s" % bgp_neighbor_ipaddr]
    router_ = "router bgp {bgp_router_asn}".format(**locals())
    neighbors_ = "neighbor {} remote-as {}".format(bgp_neighbor_ipaddr,
                                                   bgp_neighbor_remote_as)
    step("1-Setting up switch with very basic BGP configuration")
    sw1("configure terminal")
    sw1(router_)
    sw1(neighbors_)

    step("2-Verifying that the configured bgp neighbor DOES exist")
    output = sw1("do show bgp neighbors")
    assert bgp_neighbor_ipaddr in output and \
        bgp_neighbor_remote_as in output and \
        "tcp_port_number" in output and \
        "bgp_peer_keepalive_in_count" in output

    step("3-Verifying bgp neighbor deletion from the switch")
    sw1("no neighbor {bgp_neighbor_ipaddr}".format(**locals()))
    output = sw1("do show bgp neighbors")
    assert not (bgp_neighbor_ipaddr in output and
                bgp_neighbor_remote_as in output and
                "tcp_port_number" in output and
                "bgp_peer_keepalive_in_count" in output)
