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
def test_bgp_ct_router_id(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    bgp_asn = "1"
    bgp_router_id = "9.0.0.1"
    bgp_network = "11.0.0.0"
    bgp_pl = "8"

    step("1-Verifying bgp processes...")
    pid = sw1("pgrep -f bgpd", shell='bash')
    pid = pid.strip()
    assert pid != "" and pid is not None

    step("2-Applying BGP configurations")
    sw1("configure terminal")
    sw1("router bgp {}".format(bgp_asn))
    sw1("bgp router-id {}".format(bgp_router_id))
    sw1("network {}/{}".format(bgp_network, bgp_pl))

    step("3-Verifying BGP Router-ID...")
    output = sw1("do show ip bgp")
    assert bgp_router_id in output

    step("4-Unconfiguring BGP Router-ID")
    sw1("no bgp router-id {}".format(bgp_router_id))

    step("5-Verifying BGP Router-ID is unconfigured...")
    output = sw1("do show ip bgp")
    assert bgp_router_id not in output
