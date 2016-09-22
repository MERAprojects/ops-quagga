# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from zebra_routing import (
    ZEBRA_DEFAULT_TIMEOUT
)
from pytest import mark

TOPOLOGY = """
#
#
# +-------+     +-------+
# +  sw1  <----->  sw2  +
# +-------+     +-------+
#
#

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
def test_ipv6_static_route_config(topology, step):
    '''
    This test verifies various ipv6 static route configurations by validating
    both the postive and the negative test cases with default/non-default
    configurations. 'show running-config' output is checked to verify the
    setting of correct values in the DB. 'show ipv6 route' displayes FIB
    entries and it involves complex processing by zebra to install the routes
    installed in kernel. Thus, being a CLI CT, we verify the values in DB
    only.
    '''
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')

    assert sw1 is not None
    assert sw2 is not None

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw2_intf1 = format(sw2.ports["if01"])
    sw2_intf2 = format(sw2.ports["if02"])

    step('### Test to verify IPv6 static routes ###')
    # Configure switch 1
    sw1('configure terminal')
    sw1('interface %s' % sw1_intf1)
    sw1('ipv6 address 2000::1/120')
    sw1('no shutdown')
    sw1('exit')
    sw1('interface %s' % sw1_intf2)
    sw1('ipv6 address 2001::1/120')
    sw1('no shutdown')
    sw1('exit')

    # Configure switch 2
    sw2('configure terminal')
    sw2('interface %s' % sw2_intf1)
    sw2('ipv6 address 2000::2/120')
    sw2('no shutdown')
    sw2('exit')
    sw2('interface %s' % sw2_intf2)
    sw2('ipv6 address 2002::1/120')
    sw2('no shutdown')
    sw2('exit')

    step('### Verify ip route configuration with nexthop address ###')
    sw1('ipv6 route 2002::/120 2000::2 2')
    ret = sw1('do show running-config')

    assert 'ipv6 route 2002::/120 2000::2 2'in ret,\
           'IPv6 route configuration failed with nexthop address'

    step('### Verify deletion of ipv6 route with nexthop address ###')
    sw1('no ipv6 route 2002::/120 2000::2 2')
    ret = sw1('do show running-config')

    assert 'ipv6 route 2002::/120 2000::2 2' not in ret, \
           'Deletion of ipv6 route failed with nexthop address'

    step('### Verify prefix format ###')
    sw1('ipv6 route 2002:: 2000::2 2')
    ret = sw1('do show running-config')

    assert 'ipv6 route 2002:: 2000::2 2' not in ret, \
           'Prefix format verification failed'

    step('### Verify ipv6 route configuration with nexthop interface ###')
    sw1('ipv6 route 2002::/120 %s 2' % sw1_intf2)
    ret = sw1('do show running-config')

    assert 'ipv6 route 2002::/120 %s 2' % sw1_intf2 in ret, \
           'IPv6 route configuration failed with nexthop[ interface'

    step('### Verify deletion of ipv6 route with nexthop interface ###')
    sw1('no ipv6 route 2002::/120 %s 2' % sw1_intf2)
    ret = sw1('do show running-config')

    assert 'ipv6 route 2002::/120 %s 2' % sw1_intf2 not in ret, \
           'Deletion of ipv6 routes failed with nexthop interface'

    step('### Verify setting of multiple nexthops for a given prefix ###')
    sw1('ipv6 route 2002::/120 %s' % sw1_intf1)
    sw1('ipv6 route 2002::/120 %s' % sw1_intf2)
    ret = sw1('do show running-config')

    assert 'ipv6 route 2002::/120 %s' % sw1_intf1 in ret and \
        'ipv6 route 2002::/120 %s' % sw1_intf2 in ret, \
        'Multiple nexthops prefix verification failed'

    step(''' ### Verify if nexthop is not assigned locally to an interface '''
         '''as a primary ipv6 address ###\n''')
    sw1('ipv6 route 2002::/120 2001::1')
    ret = sw1('do show running-config')
    assert 'ipv6 route 2002::/120 2001::1' not in ret, \
        'Primary ipv6 address check for nexthop failed'

    step(''' ### Verify if nexthop is not assigned locally to an interface '''
         '''as a secondary ipv6 address ###\n''')
    sw1('interface %s' % sw1_intf1)
    sw1('ipv6 address 3000::3/120 secondary')
    sw1('exit')
    sw1('ipv6 route 2002::/120 3000::3')
    ret = sw1('do show running-config')
    assert 'ipv6 route 2002::/120 2001::3' not in ret, \
        'Secondary ipv6 address check for nexthop failed'
    sw1('interface %s' % sw1_intf1)
    sw1('no ipv6 address 3000::3/120 secondary')
    sw1('exit')

    step(''' ### Verify if multicast address cannot be assigned as a prefix'''
         ''' ###\n''')
    sw1('ipv6 route ff00::/128 2001::1')
    ret = sw1('do show running-config')
    assert 'ipv6 route ff00::/128 2001::1' not in ret, \
        'Multicast address check for prefix failed'

    step(''' ### Verify if multicast address cannot be assigned as a nexthop'''
         ''' ###\n''')
    sw1('ipv6 route 12ff::/128 ff00::1')
    ret = sw1('do show running-config')
    assert 'ipv6 route 12ff::/128 ff00::1' not in ret, \
        'Multicast address check for nexthop failed'

    step(''' ### Verify if linklocal address cannot be assigned as a prefix'''
         ''' ###\n''')
    sw1('ipv6 route fe80::/10 2001::1')
    ret = sw1('do show running-config')
    assert 'ipv6 route ::1/128 2001::1' not in ret, \
        'Linklocal address check for prefix failed'

    step(''' ### Verify if linklocal address cannot be assigned as a nexthop'''
         ''' ###\n''')
    sw1('ipv6 route 12ff::/128 fe80::')
    ret = sw1('do show running-config')
    assert 'ipv6 route 12ff::/128 ::1' not in ret, \
        'Linklocal address check for nexthop failed'

    step(''' ### Verify if loopback address cannot be assigned as a prefix'''
         ''' ###\n''')
    sw1('ipv6 route ::1/128 2001::1')
    ret = sw1('do show running-config')
    assert 'ipv6 route ::1/128 2001::1' not in ret, \
        'Loopback address check for prefix failed'

    step(''' ### Verify if loopback address cannot be assigned as a nexthop'''
         ''' ###\n''')
    sw1('ipv6 route 12ff::/128 ::1')
    ret = sw1('do show running-config')
    assert 'ipv6 route 12ff::/128 ::1' not in ret, \
        'Loopback address check for nexthop failed'

    step(''' ### Verify if unspecified address cannot be assigned as a '''
         '''nexthop ###\n''')
    sw1('ipv6 route 2002::/120 ::')
    ret = sw1('do show running-config')
    assert 'ipv6 route 2002::/120 ::' not in ret, \
        'Unspecified address check for nexthop failed'
