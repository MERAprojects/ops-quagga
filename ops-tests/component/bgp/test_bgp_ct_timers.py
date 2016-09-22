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
def test_bgp_ct_timers(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    step("1-Verifying bgp processes...")
    pid = sw1("pgrep -f bgpd", shell='bash')
    pid = pid.strip()
    assert pid != "" and pid is not None
    step("2-Applying BGP configurations...")
    bgp_asn = "1"
    timers_bgp_keepalive = 5
    timers_bgp_holdtime = 10
    router_ = "router bgp {bgp_asn}".format(**locals())
    timer_ = "timers bgp {} {}".format(timers_bgp_keepalive,
                                       timers_bgp_holdtime)
    sw1("configure terminal")
    sw1(router_)
    sw1(timer_)
    step("3-Verifying all configurations...")
    output = sw1("do show running-config")
    assert router_ in output and timer_ in output
    step("4-Verifying no timers bgp...")
    sw1("no timers bgp")
    output = sw1("do show running-config")
    assert timer_ not in output
    step("5-Verifying 0 timers...")
    timers_bgp_keepalive = 0
    timers_bgp_holdtime = 0
    timer_ = "timers bgp {} {}".format(timers_bgp_keepalive,
                                        timers_bgp_holdtime)
    sw1(timer_)
    output = sw1("do show running-config")
    assert timer_ in output
    step("6-Verifying no router bgp...")
    sw1("exit")
    sw1("no {router_}".format(**locals()))
    output = sw1("do show running-config")
    assert router_ not in output
