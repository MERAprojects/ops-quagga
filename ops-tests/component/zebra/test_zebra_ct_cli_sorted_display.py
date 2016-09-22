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
from re import match
from re import findall
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
sw1:if03
sw1:if04
sw2:if02

"""


def get_vrf_uuid(switch, vrf_name, step):
    """
    This function takes a switch and a vrf_name as inputs and returns
    the uuid of the vrf.
    """
    step("Getting uuid for the vrf {}".format(vrf_name))
    ovsdb_command = 'list vrf {}'.format(vrf_name)
    output = switch(ovsdb_command, shell='vsctl')
    lines = output.splitlines()
    vrf_uuid = None
    for line in lines:
        vrf_uuid = match("(.*)_uuid( +): (.*)", line)
        if vrf_uuid is not None:
            break
    assert vrf_uuid is not None
    return vrf_uuid.group(3).rstrip('\r')


def get_prefix_uuid(switch, prefix_value, step):
    """
    This function takes a switch and a prefix value as inputs and returns
    the uuid of the prefix entry.
    """
    step("Getting uuid for the prefix " + str(prefix_value))
    ovsdb_command = 'find Route prefix="' + str(prefix_value) + '"'
    output = switch(ovsdb_command, shell='vsctl')
    lines = output.splitlines()
    prefix_uuid = None
    for line in lines:
        prefix_uuid = match("(.*)_uuid( +): (.*)", line)
        if prefix_uuid is not None:
            break
    assert prefix_uuid is not None
    return prefix_uuid.group(3).rstrip('\r')


@mark.timeout(ZEBRA_DEFAULT_TIMEOUT)
@mark.gate
def test_static_route_config(topology, step):
    '''
    This test cases verifies sorted(lexicographic) retrieval of the ip routes
    stored in the DB. It verifies all the four show commands for sorted output:
    'show ip/ipv6 route', 'show rib' and 'show running-config'.
    '''
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')

    assert sw1 is not None
    assert sw2 is not None

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])

    step("### Verify that the static routes are retrieved in sorted order ###")
    # Configure switch 1
    sw1('configure terminal')
    sw1('interface %s' % sw1_intf1)
    sw1('ip address 11.0.0.1/24')
    sw1('ipv6 address 1001::1/120')
    sw1('no shutdown')
    sw1('exit')
    sw1('interface %s' % sw1_intf2)
    sw1('ip address 22.0.0.1/24')
    sw1('ipv6 address 2001::1/120')
    sw1('no shutdown')
    sw1('exit')
    sw1('interface %s' % sw1_intf3)
    sw1('ip address 33.0.0.1/24')
    sw1('ipv6 address 3001::1/120')
    sw1('no shutdown')
    sw1('exit')

    step("### Adding IPv4 routes with various prefixes and nexthops ###")
    sw1('configure terminal')
    sw1('ip route 20.20.20.0/24 %s' % sw1_intf2)
    sw1('ip route 10.0.0.0/24 %s' % sw1_intf2)
    sw1('ip route 10.0.0.0/32 %s' % sw1_intf1)
    sw1('ip route 30.30.0.0/16 %s' % sw1_intf1)

    step("### Adding IPv6 routes with various prefixes and nexthops ###")
    sw1('ipv6 route 2001::/32 %s' % sw1_intf2)
    sw1('ipv6 route 2001::/96 %s' % sw1_intf2)
    sw1('ipv6 route ::/128 %s' % sw1_intf1)
    sw1('ipv6 route 1:1::/127 %s' % sw1_intf1)

    # Stop zebra to turn 'on' the selected bit for the listed prefixes and to
    # popluate BGP and OSPF routes using ovsdb-client utility.
    sw1("systemctl stop ops-zebra", shell='bash')

    # 'show ip route' shows the routes selected by zebra for forwarding (FIB).
    # Significant amount of delay is seen when an interface is configured and
    # brought 'up' till the route gets installed in the kernel taking it as
    # nexthop and the 'selected' column is turned 'on' in the DB for that
    # particular prefix entry.
    # This being a CLI CT, introducing a hack here and manually turning on the
    # 'selected' bit to true so as to list the routes in the 'show ip route'
    # output.
    step("### Get the UUID of the configured prefixes on the switch1 ###")
    prefix_uuid = get_prefix_uuid(sw1, "11.0.0.0/24", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "22.0.0.0/24", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "33.0.0.0/24", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "20.20.20.0/24", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "10.0.0.0/24", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "10.0.0.0/32", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "30.30.0.0/16", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "1001\:\:/120", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "2001\:\:/120", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "3001\:\:/120", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "2001\:\:/32", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "2001\:\:/96", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "\:\:/128", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    prefix_uuid = get_prefix_uuid(sw1, "1\:1\:\:/127", step)
    ovsdb_command = 'set Route {} selected=true'.format(prefix_uuid)
    sw1(ovsdb_command, shell='vsctl')

    # Get the UUID of the default vrf on the sw1
    vrf_uuid = get_vrf_uuid(sw1, "vrf_default", step)

    # Prepare string for a BGP route 40.0.0.0/16 using ovsdb-client with
    # lower administration distance as compared with the corresponding
    # static route.This makes the BGP route more preferable than the static
    # route.
    bpg_route_cmd_ipv4_route = "ovsdb-client transact \'[ \"OpenSwitch\",\
         {\
             \"op\" : \"insert\",\
             \"table\" : \"Nexthop\",\
             \"row\" : {\
                 \"ip_address\" : \"1.1.1.1\",\
                 \"weight\" : 3,\
                 \"selected\": true\
             },\
             \"uuid-name\" : \"nh01\"\
         },\
        {\
            \"op\" : \"insert\",\
            \"table\" : \"Route\",\
            \"row\" : {\
                     \"prefix\":\"40.0.0.0/16\",\
                     \"from\":\"bgp\",\
                     \"vrf\":[\"uuid\",\"%s\"],\
                     \"address_family\":\"ipv4\",\
                     \"sub_address_family\":\"unicast\",\
                     \"distance\":20,\
                     \"selected\": true,\
                     \"nexthops\" : [\
                     \"set\",\
                     [\
                         [\
                             \"named-uuid\",\
                             \"nh01\"\
                         ]\
                     ]]\
                     }\
        }\
    ]\'" % vrf_uuid

    # Configure the BGP route for prefix 40.0.0.0/16 using ovsdb-client
    # interface
    sw1(bpg_route_cmd_ipv4_route, shell='bash')

    # Prepare string for a BGP route 3001::/48 using ovsdb-client with
    # lower administration distance as compared with the corresponding
    # static route.This makes the BGP route more preferable than the static
    # route.
    bpg_route_cmd_ipv6_route = "ovsdb-client transact \'[ \"OpenSwitch\",\
         {\
             \"op\" : \"insert\",\
             \"table\" : \"Nexthop\",\
             \"row\" : {\
                 \"ip_address\" : \"1::2\",\
                 \"weight\" : 3,\
                 \"selected\": true\
             },\
             \"uuid-name\" : \"nh01\"\
         },\
        {\
            \"op\" : \"insert\",\
            \"table\" : \"Route\",\
            \"row\" : {\
            \"prefix\":\"3001::/48\",\
                     \"from\":\"bgp\",\
                     \"vrf\":[\"uuid\",\"%s\"],\
                     \"address_family\":\"ipv6\",\
                     \"sub_address_family\":\"unicast\",\
                     \"distance\":20,\
                     \"selected\": true,\
                     \"nexthops\" : [\
                     \"set\",\
                     [\
                         [\
                             \"named-uuid\",\
                             \"nh01\"\
                         ]\
                     ]]\
                     }\
        }\
    ]\'" % vrf_uuid

    # Configure the BGP route for prefix 3001::/48 using ovsdb-client
    # interface
    sw1(bpg_route_cmd_ipv6_route, shell='bash')

    # Prepare string for a OSPF route 40.0.0.0/32 using ovsdb-client with
    # lower administration distance as compared with the corresponding
    # static route.This makes the OSPF route more preferable than the static
    # route.
    ospf_route_cmd_ipv4_route = "ovsdb-client transact \'[ \"OpenSwitch\",\
         {\
             \"op\" : \"insert\",\
             \"table\" : \"Nexthop\",\
             \"row\" : {\
                 \"ip_address\" : \"1.1.1.2\",\
                 \"weight\" : 10,\
                 \"selected\": true\
             },\
             \"uuid-name\" : \"nh02\"\
         },\
        {\
            \"op\" : \"insert\",\
            \"table\" : \"Route\",\
            \"row\" : {\
                     \"prefix\":\"40.0.0.0/32\",\
                     \"from\":\"ospf\",\
                     \"vrf\":[\"uuid\",\"%s\"],\
                     \"address_family\":\"ipv4\",\
                     \"sub_address_family\":\"unicast\",\
                     \"distance\":110,\
                     \"selected\": true,\
                     \"nexthops\" : [\
                     \"set\",\
                     [\
                         [\
                             \"named-uuid\",\
                             \"nh02\"\
                         ]\
                     ]]\
                     }\
        }\
    ]\'" % vrf_uuid

    # Configure the OSPF route for prefix 40.0.0.0/32 using ovsdb-client
    # interface
    sw1(ospf_route_cmd_ipv4_route, shell='bash')

    # Prepare string for a OSPF route 4001::/128 using ovsdb-client with
    # lower administration distance as compared with the corresponding
    # static route.This makes the OSPF route more preferable than the static
    # route.
    ospf_route_cmd_ipv6_route = "ovsdb-client transact \'[ \"OpenSwitch\",\
         {\
             \"op\" : \"insert\",\
             \"table\" : \"Nexthop\",\
             \"row\" : {\
                 \"ip_address\" : \"1::1\",\
                 \"weight\" : 10,\
                 \"selected\": true\
             },\
             \"uuid-name\" : \"nh02\"\
         },\
        {\
            \"op\" : \"insert\",\
            \"table\" : \"Route\",\
            \"row\" : {\
                     \"prefix\":\"4001::/128\",\
                     \"from\":\"ospf\",\
                     \"vrf\":[\"uuid\",\"%s\"],\
                     \"address_family\":\"ipv6\",\
                     \"sub_address_family\":\"unicast\",\
                     \"distance\":110,\
                     \"selected\": true,\
                     \"nexthops\" : [\
                     \"set\",\
                     [\
                         [\
                             \"named-uuid\",\
                             \"nh02\"\
                         ]\
                     ]]\
                     }\
        }\
    ]\'" % vrf_uuid

    # Configure the OSPF route for prefix 4001::/128 using ovsdb-client
    # interface
    sw1(ospf_route_cmd_ipv6_route, shell='bash')

    # List of expected ipv4 prefixes in sorted order
    expected_ipv4_prefixes = ['10.0.0.0/24', '10.0.0.0/32', '11.0.0.0/24',
                              '20.20.20.0/24', '22.0.0.0/24', '30.30.0.0/16',
                              '33.0.0.0/24', '40.0.0.0/16', '40.0.0.0/32']

    step('### Comparing output of "show ip route" with the expected'
         ' output ###')
    configured_ipv4_prefixes = []
    sw1('configure terminal')
    ret = sw1('do show ip route')
    lines = ret.split('\n')

    for line in lines:
        prefix = match("^\d{0,9}\.\d{0,9}\.\d{0,9}\.\d{0,9}/\d{0,9}", line)
        if prefix is not None:
            # Populating the prefixes from the CLI output
            configured_ipv4_prefixes.append(prefix.group(0))

    # Verifying configured_ipv4_prefixes[] with the expected_ipv4_prefixes[]
    assert expected_ipv4_prefixes == configured_ipv4_prefixes, \
        "Expected ipv4 routes selected for FIB not present in the DB"

    # List of expected ipv6 prefixes in sorted order
    expected_ipv6_prefixes = ['::/128', '1:1::/127', '1001::/120', '2001::/32',
                              '2001::/96', '2001::/120', '3001::/48',
                              '3001::/120', '4001::/128']

    step('### Comparing output of "show ipv6 route" with the expected'
         ' output ###')
    configured_ipv6_prefixes = []
    ret = sw1('do show ipv6 route')

    configured_ipv6_prefixes = findall(r'(.*),\s*.*next-hops', ret)

    # Verifying configured_ipv6_prefixes[] with the expected_ipv6_prefixes[]
    assert expected_ipv6_prefixes == configured_ipv6_prefixes, \
        "Expected ipv6 routes selected for FIB not present in the DB"

    # List of expected ipv4 and ipv6 prefixes in sorted order. The prefixes
    # preceded with '*' are selected for forwarding and output is expected
    # to be in sorted order with ipv4 entries preceding the ipv6 entries.
    expected_rib_prefixes = ['*10.0.0.0/24', '*10.0.0.0/32', '*11.0.0.0/24',
                             '*20.20.20.0/24', '*22.0.0.0/24', '*30.30.0.0/16',
                             '*33.0.0.0/24', '*40.0.0.0/16', '*40.0.0.0/32',
                             '*::/128', '*1:1::/127', '*1001::/120',
                             '*2001::/32', '*2001::/96', '*2001::/120',
                             '*3001::/48', '*3001::/120', '*4001::/128']

    step('### Comparing output of "show rib" with the expected'
         ' output ###')
    configured_rib_prefixes = []
    ret = sw1('do show rib')

    configured_rib_prefixes = findall(r'(.*),\s*.*next-hops', ret)

    # Verifying configured_rib_prefixes[] with the expected_rib_prefixes[]
    assert expected_rib_prefixes == configured_rib_prefixes, \
        "Expected ipv4 and ipv6 routes in RIB not present in the DB"

    step('### Comparing output of "show running-config" with the expected'
         ' output ###')
    # List of routes added expected in sorted manner
    expected_showrun_prefixes = \
        ['ip route 10.0.0.0/24 %s' % sw1_intf2,
         'ip route 10.0.0.0/32 %s' % sw1_intf1,
         'ip route 20.20.20.0/24 %s' % sw1_intf2,
         'ip route 30.30.0.0/16 %s' % sw1_intf1,
         'ipv6 route ::/128 %s' % sw1_intf1,
         'ipv6 route 1:1::/127 %s' % sw1_intf1,
         'ipv6 route 2001::/32 %s' % sw1_intf2,
         'ipv6 route 2001::/96 %s' % sw1_intf2]
    configured_showrun_prefixes = []
    ret = sw1('do show running-config')
    lines = ret.split('\n')
    for line in lines:
        if line in expected_showrun_prefixes:
            configured_showrun_prefixes.append(line)

    # Verifying configured_showrun_prefixes[] with the
    # expected_showrun_prefixes[]
    assert expected_showrun_prefixes == configured_showrun_prefixes, \
        "Expected routes in 'show running-config' not present in the DB"
