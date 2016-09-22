# -*- coding: utf-8 -*-

# (c) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
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

from zebra_routing import (
    ZEBRA_DEFAULT_TIMEOUT
)
from pytest import mark

TOPOLOGY = """
#               +-------+     +-------+
# +-------+     |       <----->  hs2  |
# |  hs1  <----->       |     +-------+
# +-------+     |  sw1  <----+
#               |       |    | +-------+
#               |       <-+  +->       |    +-------+
#               +-------+ |    |  sw2  <---->  hs3  |
#                         +---->       |    +-------+
#                              +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=host name="Host 1"] hs1
[type=host name="Host 2"] hs2
[type=host name="Host 3"] hs3

# Links
sw1:if01 -- hs1:eth1
sw1:if03 -- sw2:if01
sw1:if04 -- sw2:if02
sw1:if02 -- hs2:eth1
sw2:if03 -- hs3:eth1
"""


def _configure_switches(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    sw2 = topology.get("sw2")
    assert sw2 is not None

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])
    sw2_intf1 = format(sw2.ports["if01"])
    sw2_intf2 = format(sw2.ports["if02"])
    sw2_intf3 = format(sw2.ports["if03"])

    step('1-Configuring Switches')
    # Configure switch sw1
    sw1("configure terminal")

    # Configure interface 1 on switch sw1
    sw1('interface %s' % sw1_intf1)
    sw1("ip address 10.0.10.2/24")
    sw1("no shut")
    sw1("exit")

    # Configure interface 2 on switch sw1
    sw1('interface %s' % sw1_intf2)
    sw1("ip address 10.0.20.2/24")
    sw1("no shut")
    sw1("exit")

    # Configure interface 3 on switch sw1
    sw1('interface %s' % sw1_intf3)
    sw1("ip address 10.0.30.1/24")
    sw1("no shut")
    sw1("exit")

    # Configure interface 4 on switch sw1
    sw1('interface %s' % sw1_intf4)
    sw1("ip address 10.0.40.1/24")
    sw1("no shut")
    sw1("exit")

    # Add IPv4 static route on sw1 and sw2
    sw1("ip route 10.0.70.0/24 10.0.30.2")
    sw1("ip route 10.0.70.0/24 10.0.40.2")

    # Add second ecmp IPv4 static route on sw1 and sw2
    # sw1("ip route 10.0.70.0/24 10.0.40.2")
    # Configure switch sw2
    sw2("configure terminal")

    # Configure interface 1 on switch sw2
    sw2('interface %s' % sw2_intf1)
    sw2("ip address 10.0.30.2/24")
    sw2("no shut")
    sw2("exit")

    # Configure interface 2 on switch sw2
    sw2('interface %s' % sw2_intf2)
    sw2("ip address 10.0.40.2/24")
    sw2("no shut")
    sw2("exit")

    # Configure interface 3 on switch s4
    sw2('interface %s' % sw2_intf3)
    sw2("ip address 10.0.70.2/24")
    sw2("no shut")
    sw2("exit")

    sw2("ip route 10.0.10.0/24 10.0.30.1")
    sw2("ip route 10.0.10.0/24 10.0.40.1")
    sw2("ip route 10.0.20.0/24 10.0.30.1")
    sw2("ip route 10.0.20.0/24 10.0.40.1")


def _configure_hosts(topology, step):
    hs1 = topology.get("hs1")
    assert hs1 is not None
    hs2 = topology.get("hs2")
    assert hs2 is not None
    hs3 = topology.get("hs3")
    assert hs3 is not None

    step('2-Configuring hosts')

    # Configure host 1
    hs1.libs.ip.interface('eth1', addr="10.0.10.1/24", up=True)

    # Configure host 2
    hs2.libs.ip.interface('eth1', addr="10.0.20.1/24", up=True)

    # hs2("ip addr add 10.0.20.1/24 dev if01")
    # hs2("ip addr del 10.0.0.2/8 dev if01")
    # Configure host 3
    hs3.libs.ip.interface('eth1', addr="10.0.70.1/24", up=True)

    # hs3("ip addr add 10.0.70.1/24 dev if01")
    # hs3("ip addr del 10.0.0.3/8 dev if01")
    # Add V4 default gateway on hosts hs1 and hs2
    hs1("ip route add 10.0.30.0/24 via 10.0.10.2")
    hs1("ip route add 10.0.40.0/24 via 10.0.10.2")
    hs1("ip route add 10.0.70.0/24 via 10.0.10.2")
    hs2("ip route add 10.0.30.0/24 via 10.0.20.2")
    hs2("ip route add 10.0.40.0/24 via 10.0.10.2")
    hs2("ip route add 10.0.70.0/24 via 10.0.20.2")
    hs3("ip route add 10.0.10.0/24 via 10.0.70.2")
    hs3("ip route add 10.0.20.0/24 via 10.0.70.2")
    hs3("ip route add 10.0.30.0/24 via 10.0.70.2")
    hs3("ip route add 10.0.40.0/24 via 10.0.70.2")


def _v4_route_ping_test(topology, step):
    hs1 = topology.get("hs1")
    assert hs1 is not None
    hs2 = topology.get("hs2")
    assert hs2 is not None
    step('3-IPv4 Ping test')

    # Ping host3 from host1, pinging twice to take care of unresolved ARPs
    ping = hs1.libs.ping.ping(10, '10.0.70.1')
    assert ping['received'] > 0, "Ping from Host3 to Host1 failed"
    ping = hs1.libs.ping.ping(10, '10.0.70.1')
    assert ping['transmitted'] == ping['received'], "Ping from Host3 to Host1"\
                                                    " failed"

    # Ping host3 from host2, pinging twice to take care of unresolved ARPs
    ping = hs2.libs.ping.ping(10, '10.0.70.1')
    assert ping['received'] > 0, "Ping from Host2 to Host1 failed"
    ping = hs2.libs.ping.ping(10, '10.0.70.1')
    assert ping['transmitted'] == ping['received'], "Ping from Host2 to Host1"\
                                                    " failed"


def _v4_route_delete_ping_test(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    hs1 = topology.get("hs1")
    assert hs1 is not None
    step('4-Verify TCPDUMP on SW2 to confirm ecmp load balance')
    step('\n######### Verify deletion of IPv4 static routes ##########\n')

    # Delete IPv4 route on switchs1 towards host2 network
    # sw1("configure terminal")
    sw1("no ip route 10.0.70.0/24 10.0.40.2")
    sw1("no ip route 10.0.70.0/24 10.0.30.2")

    # Ping host1 from host2
    ping = hs1.libs.ping.ping(10, '10.0.70.1')
    assert ping['transmitted'] is 10 and ping['received'] is 0, "Ping from "\
        "Host1 to Host2 success"


@mark.timeout(ZEBRA_DEFAULT_TIMEOUT)
@mark.gate
def test_zebra_ct_ecmp(topology, step):
    _configure_switches(topology, step)
    _configure_hosts(topology, step)
    _v4_route_ping_test(topology, step)
    _v4_route_delete_ping_test(topology, step)
