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
# +-------+      +-------+
# |  sw1  <------>  sw2  |
# +-------+      +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2

# Links
sw1:if01 -- sw2:if01
sw1:if02
sw2:if02
"""


@mark.timeout(ZEBRA_DEFAULT_TIMEOUT)
@mark.gate
def test_zebra_ct_fib_selection(topology, step):
    sw1 = topology.get("sw1")
    sw2 = topology.get("sw2")

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw2_intf1 = format(sw2.ports["if01"])
    sw2_intf2 = format(sw2.ports["if02"])

    step('1-Configuring the topology')

    # Configure switch sw1
    sw1("configure terminal")

    # Configure interface 1 on switch sw1
    sw1('interface %s' % sw1_intf1)
    sw1("no shutdown")
    sw1("ip address 10.0.10.1/24")
    sw1("ipv6 address 2000::1/120")
    sw1("exit")

    # Configure interface 2 on switch sw1
    sw1('interface %s' % sw1_intf2)
    sw1("no shutdown")
    sw1("ip address 10.0.20.1/24")
    sw1("ipv6 address 2001::1/120")
    sw1("exit")

    # Configure switch sw2
    sw2("configure terminal")

    # Configure interface 1 on switch sw2
    sw2('interface %s' % sw2_intf1)
    sw2("no shutdown")
    sw2("ip address 10.0.10.2/24")
    sw2("ipv6 address 2000::2/120")
    sw2("exit")

    # Configure interface 2 on switch sw2
    sw2('interface %s' % sw2_intf2)
    sw2("no shutdown")
    sw2("ip address 10.0.30.1/24")
    sw2("ipv6 address 2002::1/120")
    sw2("exit")

    # Add IPv4 static route on sw1 and sw2
    sw1("ip route 10.0.30.0/24 10.0.10.2")
    sw2("ip route 10.0.20.0/24 10.0.10.1")

    # Add IPv6 static route on sw1 and sw2
    sw1("ipv6 route 2002::/120 2000::2")
    sw2("ipv6 route 2001::/120 2000::1")

    # Turning on the interfaces
    sw1("set interface %s user_config:admin=up" % sw1_intf1,
        shell='vsctl')
    sw1("set interface %s user_config:admin=up" % sw1_intf2,
        shell='vsctl')
    sw2("set interface %s user_config:admin=up" % sw2_intf1,
        shell='vsctl')
    sw2("set interface %s user_config:admin=up" % sw2_intf2,
        shell='vsctl')

    step('2-Verify static routes are selected for fib')

    # Parse the "ovsdb-client dump Route" output and extract the lines of the
    # "Route table". This section will have all the Route table entries. Then
    # parse line by line to match the contents
    dump = sw1("ovsdb-client dump Route", shell='bash')
    lines = dump.split('\n')
    check = False
    for line in lines:
        if check:
            if 'static' in line and 'unicast' in line and \
               '10.0.30.0/24' in line:
                assert 'true' in line
            elif 'static' in line and 'unicast' in line and \
                 '2002::/120' in line:
                assert 'true' in line
        if 'Route table' in line:
            check = True
