# -*- coding: utf-8 -*-

# (c) Copyright 2015-2016 Hewlett Packard Enterprise Development LP
#
# GNU Zebra is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any
# later version.
#
# GNU Zebra is distributed in the hope that it will be useful, but
# WITHoutput ANY WARRANTY; withoutput even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Zebra; see the file COPYING.  If not, write to the Free
# Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.

from zebra_routing import (
    verify_show_ip_route,
    verify_show_rib,
    ZEBRA_DEFAULT_TIMEOUT
)
from re import match
from pytest import mark


# Topology definition. the topology contains two back to back switches
# having four links between them.
TOPOLOGY = """
# +-------+    +-------+
# |       <---->       |
# |       <---->       |
# |  sw1  |    |  sw2  |
# |       <---->       |
# |       <---->       |
# +-------+    +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2

# Links
sw1:if01 -- sw2:if01
sw1:if02 -- sw2:if02
sw1:if03 -- sw2:if03
sw1:if04 -- sw2:if04
"""


"""
    Format of the route dictionary used for component test verification

    data keys
        Route - string set to route which is of the format
                "Prefix/Masklen"
        NumberNexthops - string set to the number of next-hops
                         of the route
        Next-hop - string set to the next-hop port or IP/IPv6
                   address as the key and a dictionary as value
        data keys
            Distance - String whose numeric value is the administration
                       distance of the next-hop
            Metric - String whose numeric value is the metric of the
                     next-hop
            RouteType - String which is the route type of the next-hop
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


def get_uuid_from_nexthop_table(switch, nexthop_ip, step):
    """
    This function takes a switch and nexthop IPv4 address and retruns
    the uuid for the next-hop
    """
    step("Getting uuid for the nexthop {}".format(nexthop_ip))

    ovsdb_nexthop_command = "ovsdb-client dump Nexthop"
    output = switch(ovsdb_nexthop_command, shell='bash')
    lines = output.splitlines()
    nexthop_uuid = None
    nexthop_regex = "(.*) {}(.*)%s(.*)" % (nexthop_ip)
    for line in lines:
        nexthop_uuid = match(nexthop_regex, line)
        if nexthop_uuid is not None:
            break
    assert nexthop_uuid is not None
    return nexthop_uuid.group(1).rstrip('\r')


# This test configures IPv4 static/BGP routes and checks if the
# routes and next-hops show correctly selected in the output of
# "show ip route/show rib".
def add_static_bgp_routes(sw1, sw2, step):

    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])

    # Interfaces to configure
    sw1_interfaces = []

    # IPs to configure
    sw1_ifs_ips = ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"]
    size = len(sw1_ifs_ips)

    # Adding interfaces to configure
    for i in range(size):
        sw1_interfaces.append(sw1.ports["if0{}".format(i + 1)])
    sw1_mask = 24

    step("Configuring interfaces and IPs on SW1")
    sw1("configure terminal")
    for i in range(size):
        sw1("interface {}".format(sw1_interfaces[i]))
        sw1("ip address {}/{}".format(sw1_ifs_ips[i], sw1_mask))
        sw1("no shutdown")
        sw1("exit")
        output = sw1("do show running-config")
        assert "interface {}".format(sw1_interfaces[i]) in output
        assert "ip address {}/{}".format(sw1_ifs_ips[i], sw1_mask) in output

    step("Cofiguring sw1 IPV4 static routes")

    # Routes to configure
    nexthops = ["1.1.1.2", sw1_interfaces[1],
                sw1_interfaces[2], "4.4.4.1"]
    for i in range(size):
        sw1("ip route 123.0.0.1/32 {} 10".format(nexthops[i]))
        output = sw1("do show running-config")
        assert "ip route 123.0.0.1/32 {} 10".format(nexthops[i]) in output

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '4'
    rib_ipv4_static_route1['1.1.1.2'] = dict()
    rib_ipv4_static_route1['1.1.1.2']['Distance'] = '10'
    rib_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    rib_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    rib_ipv4_static_route1[sw1_intf2] = dict()
    rib_ipv4_static_route1[sw1_intf2]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv4_static_route1[sw1_intf3] = dict()
    rib_ipv4_static_route1[sw1_intf3]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '10'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops. Since static is configured with a
    # higher administration distance than BGP route, so the static route
    # cannot be in FIB.
    route_ipv4_static_route1 = dict()
    route_ipv4_static_route1['Route'] = '123.0.0.1/32'

    sw1("ip route 143.0.0.1/32 4.4.4.1")
    output = sw1("do show running-config")
    assert "ip route 143.0.0.1/32 4.4.4.1" in output

    # Configure IPv4 route 143.0.0.1/32 with 1 next-hop.
    # Populate the expected RIB ("show rib") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    step("Configuring switch 1 IPv4 BGP routes")

    # Get the UUID od the default vrf on the sw1
    vrf_uuid = get_vrf_uuid(sw1, "vrf_default", step)

    # Prepare string for a BGP route 123.0.0.1/32 using ovsdb-client with
    # lower administration distance as compared with the corresponding
    # static route.This makes the BGP route more preferable than the static
    # route.
    bpg_route_cmd_ipv4_route1 = "ovsdb-client transact \'[ \"OpenSwitch\",\
         {\
             \"op\" : \"insert\",\
             \"table\" : \"Nexthop\",\
             \"row\" : {\
                 \"ip_address\" : \"3.3.3.5\",\
                 \"weight\" : 3,\
                 \"selected\": true\
             },\
             \"uuid-name\" : \"nh01\"\
         },\
        {\
            \"op\" : \"insert\",\
            \"table\" : \"Route\",\
            \"row\" : {\
                     \"prefix\":\"123.0.0.1/32\",\
                     \"from\":\"bgp\",\
                     \"vrf\":[\"uuid\",\"%s\"],\
                     \"address_family\":\"ipv4\",\
                     \"sub_address_family\":\"unicast\",\
                     \"distance\":6,\
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

    # Configure the BGP route for prefix 123.0.0.1/32 using ovsdb-client
    # interface
    sw1(bpg_route_cmd_ipv4_route1, shell='bash')

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route1 = dict()
    rib_ipv4_bgp_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_bgp_route1['NumberNexthops'] = '1'
    rib_ipv4_bgp_route1['3.3.3.5'] = dict()
    rib_ipv4_bgp_route1['3.3.3.5']['Distance'] = '6'
    rib_ipv4_bgp_route1['3.3.3.5']['Metric'] = '0'
    rib_ipv4_bgp_route1['3.3.3.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the BGP
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_bgp_route1 = rib_ipv4_bgp_route1

    # Prepare string for a BGP route 143.0.0.1/32 using ovsdb-client with
    # administration distance as greater than the corresponding static route.
    # This makes the BGP route less preferable than the corresponding
    # static route.
    bpg_route_command_ipv4_route2 = "ovsdb-client transact \'[ \"OpenSwitch\",\
         {\
             \"op\" : \"insert\",\
             \"table\" : \"Nexthop\",\
             \"row\" : {\
                 \"ip_address\" : \"1.1.1.5\",\
                 \"weight\" : 3,\
                 \"selected\": true\
             },\
             \"uuid-name\" : \"nh01\"\
         },\
        {\
            \"op\" : \"insert\",\
            \"table\" : \"Route\",\
            \"row\" : {\
                     \"prefix\":\"143.0.0.1/32\",\
                     \"from\":\"bgp\",\
                     \"vrf\":[\"uuid\",\"%s\"],\
                     \"address_family\":\"ipv4\",\
                     \"sub_address_family\":\"unicast\",\
                     \"distance\":6,\
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

    # Configure the BGP route for prefix 143.0.0.1/32 using ovsdb-client
    # interface
    sw1(bpg_route_command_ipv4_route2, shell='bash')

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 143.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route2 = dict()
    rib_ipv4_bgp_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_bgp_route2['NumberNexthops'] = '1'
    rib_ipv4_bgp_route2['1.1.1.5'] = dict()
    rib_ipv4_bgp_route2['1.1.1.5']['Distance'] = '6'
    rib_ipv4_bgp_route2['1.1.1.5']['Metric'] = '0'
    rib_ipv4_bgp_route2['1.1.1.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops. Since static is configured with a
    # lower administration distance than BGP route, so the BGP route cannot be
    # in FIB.
    route_ipv4_bgp_route2 = dict()
    route_ipv4_bgp_route2['Route'] = '143.0.0.1/32'

    step("Verifying the IPv4 static and BGP routes on switch 1")
    sw1("configure terminal")
    aux_route = route_ipv4_static_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    aux_route = route_ipv4_bgp_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route1)
    aux_route = rib_ipv4_bgp_route1['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route1)
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    aux_route = route_ipv4_bgp_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route2)
    aux_route = rib_ipv4_bgp_route2['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route2)


# This test case shuts few next-hop interfaces for static and BGP routes.
# Zebra should re-compute the best protocol next-hop and set/unset the
# selected bits.
def shutdown_static_bgp_routes_next_hop_interfaces(sw1, sw2, step):

    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("Testing the BGP and static route selection on shutting nexthop \
         interfaces on sw1")

    # sHutdown next-hop interface 3
    step("Shut down interface 3")
    sw1("configure terminal")
    sw1("interface %s" % sw1_intf3)
    sw1("shutdown")

    # Shutdown next-hop interface 4
    step("Shut down interface 4")
    sw1("configure terminal")
    sw1("interface %s" % sw1_intf4)
    sw1("shutdown")

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '4'
    rib_ipv4_static_route1['1.1.1.2'] = dict()
    rib_ipv4_static_route1['1.1.1.2']['Distance'] = '10'
    rib_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    rib_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    rib_ipv4_static_route1[sw1_intf2] = dict()
    rib_ipv4_static_route1[sw1_intf2]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv4_static_route1[sw1_intf3] = dict()
    rib_ipv4_static_route1[sw1_intf3]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '10'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = dict()
    route_ipv4_static_route1['Route'] = '123.0.0.1/32'
    route_ipv4_static_route1['NumberNexthops'] = '2'
    route_ipv4_static_route1['1.1.1.2'] = dict()
    route_ipv4_static_route1['1.1.1.2']['Distance'] = '10'
    route_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    route_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    route_ipv4_static_route1[sw1_intf2] = dict()
    route_ipv4_static_route1[sw1_intf2]['Distance'] = '10'
    route_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    route_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'

    # Configure IPv4 route 143.0.0.1/32 with 1 next-hop.
    # Populate the expected RIB ("show rib") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_static_route2 = dict()
    route_ipv4_static_route2['Route'] = '143.0.0.1/32'

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route1 = dict()
    rib_ipv4_bgp_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_bgp_route1['NumberNexthops'] = '1'
    rib_ipv4_bgp_route1['3.3.3.5'] = dict()
    rib_ipv4_bgp_route1['3.3.3.5']['Distance'] = '6'
    rib_ipv4_bgp_route1['3.3.3.5']['Metric'] = '0'
    rib_ipv4_bgp_route1['3.3.3.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the BGP
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_bgp_route1 = dict()
    route_ipv4_bgp_route1['Route'] = '123.0.0.1/32'

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 143.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route2 = dict()
    rib_ipv4_bgp_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_bgp_route2['NumberNexthops'] = '1'
    rib_ipv4_bgp_route2['1.1.1.5'] = dict()
    rib_ipv4_bgp_route2['1.1.1.5']['Distance'] = '6'
    rib_ipv4_bgp_route2['1.1.1.5']['Metric'] = '0'
    rib_ipv4_bgp_route2['1.1.1.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops. Since static is configured with a
    # lower administration distance than BGP route, so the BGP route cannot be
    # in FIB.
    route_ipv4_bgp_route2 = rib_ipv4_bgp_route2

    step("Verifying the IPv4 static and BGP routes on switch 1")
    aux_route = route_ipv4_static_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    aux_route = route_ipv4_bgp_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route1)
    aux_route = rib_ipv4_bgp_route1['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route1)
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    aux_route = route_ipv4_bgp_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route2)
    aux_route = rib_ipv4_bgp_route2['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route2)


# This test case brings up few next-hop interfaces for static and BGP routes.
# Zebra should re-compute the best protocol next-hop and set/unset the
# selected bits.
def no_shutdown_static_bgp_routes_next_hop_interfaces(sw1, sw2, step):

    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("Testing the BGP and static route selection on no-shutting nexthop \
         interfaces on sw1")

    # sHutdown next-hop interface 3
    step("Shut down interface 3")
    sw1("configure terminal")
    sw1("interface %s" % sw1_intf3)
    sw1("no shutdown")

    # Shutdown next-hop interface 4
    step("Shut down interface 4")
    sw1("configure terminal")
    sw1("interface %s" % sw1_intf4)
    sw1("no shutdown")

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '4'
    rib_ipv4_static_route1['1.1.1.2'] = dict()
    rib_ipv4_static_route1['1.1.1.2']['Distance'] = '10'
    rib_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    rib_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    rib_ipv4_static_route1[sw1_intf2] = dict()
    rib_ipv4_static_route1[sw1_intf2]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv4_static_route1[sw1_intf3] = dict()
    rib_ipv4_static_route1[sw1_intf3]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '10'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = dict()
    route_ipv4_static_route1['Route'] = '123.0.0.1/32'

    # Configure IPv4 route 143.0.0.1/32 with 1 next-hop.
    # Populate the expected RIB ("show rib") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route1 = dict()
    rib_ipv4_bgp_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_bgp_route1['NumberNexthops'] = '1'
    rib_ipv4_bgp_route1['3.3.3.5'] = dict()
    rib_ipv4_bgp_route1['3.3.3.5']['Distance'] = '6'
    rib_ipv4_bgp_route1['3.3.3.5']['Metric'] = '0'
    rib_ipv4_bgp_route1['3.3.3.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the BGP
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_bgp_route1 = rib_ipv4_bgp_route1

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 143.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route2 = dict()
    rib_ipv4_bgp_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_bgp_route2['NumberNexthops'] = '1'
    rib_ipv4_bgp_route2['1.1.1.5'] = dict()
    rib_ipv4_bgp_route2['1.1.1.5']['Distance'] = '6'
    rib_ipv4_bgp_route2['1.1.1.5']['Metric'] = '0'
    rib_ipv4_bgp_route2['1.1.1.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops. Since static is configured with a
    # lower administration distance than BGP route, so the BGP route cannot be
    # in FIB.
    route_ipv4_bgp_route2 = dict()
    route_ipv4_bgp_route2['Route'] = '143.0.0.1/32'

    step("Verifying the IPv4 static and BGP routes on switch 1")
    aux_route = route_ipv4_static_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    aux_route = route_ipv4_bgp_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route1)
    aux_route = rib_ipv4_bgp_route1['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route1)
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    aux_route = route_ipv4_bgp_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route2)
    aux_route = rib_ipv4_bgp_route2['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route2)


# This test case adds a next-hop to the BGP routes to makes IPv4 BGP routes
# multi-path and checks if the routes and next-hops show correctly selected
# in the output of "show ip route/show rib".
def add_nexthop_to_make_bgp_route_ecmp(sw1, sw2, step):

    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])

    step("Configuring another next-hop for IPv4 BGP route 123.0.0.1/32 on \
         switch 1")

    nexthop_uuid = get_uuid_from_nexthop_table(sw1, "3.3.3.5", step)

    # Prepare string to add another BGP next-hop for route  123.0.0.1/32
    # using ovsdb-client.
    bpg_route_cmd_ipv4_route1 = """ovsdb-client transact '[ "OpenSwitch",
         {
             "op" : "insert",
             "table" : "Nexthop",
             "row" : {
                 "ip_address" : "4.4.4.9",
                 "weight" : 3,
                 "selected": true
             },
             "uuid-name" : "nh01"
         },
         {
            "op" : "update",
            "table" : "Route",
            "where":[["prefix","==","123.0.0.1/32"],["from","==","bgp"]],
            "row" : {
                     "nexthops" : [
                     "set",
                     [["uuid", "%s"],
                      ["named-uuid", "nh01"]
                     ]]
                    }
         }
    ]'""" % nexthop_uuid

    # Configure the BGP next-hop for prefix 123.0.0.1/32 using ovsdb-client
    # interface
    sw1(bpg_route_cmd_ipv4_route1, shell='bash')

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '4'
    rib_ipv4_static_route1['1.1.1.2'] = dict()
    rib_ipv4_static_route1['1.1.1.2']['Distance'] = '10'
    rib_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    rib_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    rib_ipv4_static_route1[sw1_intf2] = dict()
    rib_ipv4_static_route1[sw1_intf2]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv4_static_route1[sw1_intf3] = dict()
    rib_ipv4_static_route1[sw1_intf3]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '10'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = dict()
    route_ipv4_static_route1['Route'] = '123.0.0.1/32'

    # Configure IPv4 route 143.0.0.1/32 with 1 next-hop.
    # Populate the expected RIB ("show rib") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route1 = dict()
    rib_ipv4_bgp_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_bgp_route1['NumberNexthops'] = '2'
    rib_ipv4_bgp_route1['3.3.3.5'] = dict()
    rib_ipv4_bgp_route1['3.3.3.5']['Distance'] = '6'
    rib_ipv4_bgp_route1['3.3.3.5']['Metric'] = '0'
    rib_ipv4_bgp_route1['3.3.3.5']['RouteType'] = 'bgp'
    rib_ipv4_bgp_route1['4.4.4.9'] = dict()
    rib_ipv4_bgp_route1['4.4.4.9']['Distance'] = '6'
    rib_ipv4_bgp_route1['4.4.4.9']['Metric'] = '0'
    rib_ipv4_bgp_route1['4.4.4.9']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the BGP
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_bgp_route1 = rib_ipv4_bgp_route1

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 143.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route2 = dict()
    rib_ipv4_bgp_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_bgp_route2['NumberNexthops'] = '1'
    rib_ipv4_bgp_route2['1.1.1.5'] = dict()
    rib_ipv4_bgp_route2['1.1.1.5']['Distance'] = '6'
    rib_ipv4_bgp_route2['1.1.1.5']['Metric'] = '0'
    rib_ipv4_bgp_route2['1.1.1.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_bgp_route2 = dict()
    route_ipv4_bgp_route2['Route'] = '143.0.0.1/32'

    step("Verifying the IPv4 static and BGP routes on switch 1")
    sw1("configure terminal")
    aux_route = route_ipv4_static_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    aux_route = route_ipv4_bgp_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route1)
    aux_route = rib_ipv4_bgp_route1['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route1)
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    aux_route = route_ipv4_bgp_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route2)
    aux_route = rib_ipv4_bgp_route2['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route2)


# This test case removes a next-hop to the BGP routes to makes IPv4 BGP routes
# single path and checks if the routes and next-hops show correctly selected
# in the output of "show ip route/show rib".
def remove_nexthop_to_make_bgp_route_single(sw1, sw2, step):

    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])

    step("Removing a next-hop for IPv4 BGP route 123.0.0.1/32 on \
         switch 1")

    nexthop_uuid = get_uuid_from_nexthop_table(sw1, "3.3.3.5", step)

    # Prepare string to remove a BGP next-hop for route  123.0.0.1/32
    # using ovsdb-client.
    bpg_route_cmd_ipv4_route1 = """ovsdb-client transact '[ "OpenSwitch",
         {
            "op" : "update",
            "table" : "Route",
            "where":[["prefix","==","123.0.0.1/32"],["from","==","bgp"]],
            "row" : {
                     "nexthops" : [
                     "set",
                     [["uuid", "%s"]
                     ]]
                    }
         }
    ]'""" % nexthop_uuid

    # Configure the BGP next-hop for prefix 123.0.0.1/32 using ovsdb-client
    # interface
    sw1(bpg_route_cmd_ipv4_route1, shell='bash')

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '4'
    rib_ipv4_static_route1['1.1.1.2'] = dict()
    rib_ipv4_static_route1['1.1.1.2']['Distance'] = '10'
    rib_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    rib_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    rib_ipv4_static_route1[sw1_intf2] = dict()
    rib_ipv4_static_route1[sw1_intf2]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv4_static_route1[sw1_intf3] = dict()
    rib_ipv4_static_route1[sw1_intf3]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '10'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = dict()
    route_ipv4_static_route1['Route'] = '123.0.0.1/32'

    # Configure IPv4 route 143.0.0.1/32 with 1 next-hop.
    # Populate the expected RIB ("show rib") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route1 = dict()
    rib_ipv4_bgp_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_bgp_route1['NumberNexthops'] = '1'
    rib_ipv4_bgp_route1['3.3.3.5'] = dict()
    rib_ipv4_bgp_route1['3.3.3.5']['Distance'] = '6'
    rib_ipv4_bgp_route1['3.3.3.5']['Metric'] = '0'
    rib_ipv4_bgp_route1['3.3.3.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the BGP
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_bgp_route1 = rib_ipv4_bgp_route1

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 143.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route2 = dict()
    rib_ipv4_bgp_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_bgp_route2['NumberNexthops'] = '1'
    rib_ipv4_bgp_route2['1.1.1.5'] = dict()
    rib_ipv4_bgp_route2['1.1.1.5']['Distance'] = '6'
    rib_ipv4_bgp_route2['1.1.1.5']['Metric'] = '0'
    rib_ipv4_bgp_route2['1.1.1.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_bgp_route2 = dict()
    route_ipv4_bgp_route2['Route'] = '143.0.0.1/32'

    step("Verifying the IPv4 static and BGP routes on switch 1")
    sw1("configure terminal")
    aux_route = route_ipv4_static_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    aux_route = route_ipv4_bgp_route1['Route']
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route1)
    aux_route = rib_ipv4_bgp_route1['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route1)
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2['Route']
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    aux_route = route_ipv4_bgp_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route2)
    aux_route = rib_ipv4_bgp_route2['Route']
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route2)


# This test deletes IPv4 static/BGP routes and checks if the
# routes and next-hops show correctly selected in the output of
# "show ip route/show rib".
def delete_static_bgp_routes(sw1, sw2, step):

    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])

    step("Testing the BGP and static route deletion on sw1")
    step("Deleting 123.0.0.0.1/32 BGP route on sw1")

    # Command to delete the BGP route 123.0.0.1/32. This should make the static
    # route more preferable in RIB.
    bgp_route_delete_command = "ovsdb-client transact \'[ \"OpenSwitch\",\
        {\
            \"op\" : \"delete\",\
            \"table\" : \"Route\",\
             \"where\":[[\"prefix\",\"==\",\"123.0.0.1/32\"],[\"from\",\"==\",\"bgp\"]]\
        }\
    ]\'"

    # Delete the BGP route for prefix 123.0.0.1/32 using ovsdb-client interface
    sw1(bgp_route_delete_command, shell='bash')

    # Delete the static route for 143.0.0.1/32 so that BGP route becomes the
    # more preferable route in RIB.
    step("Deleting 143.0.0.0.1/32 static route on sw1")
    sw1("configure terminal")
    sw1("no ip route 143.0.0.1/32 4.4.4.1")

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '4'
    rib_ipv4_static_route1['1.1.1.2'] = dict()
    rib_ipv4_static_route1['1.1.1.2']['Distance'] = '10'
    rib_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    rib_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    rib_ipv4_static_route1[sw1_intf2] = dict()
    rib_ipv4_static_route1[sw1_intf2]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv4_static_route1[sw1_intf3] = dict()
    rib_ipv4_static_route1[sw1_intf3]['Distance'] = '10'
    rib_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '10'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 123.0.0.1/32 and its next-hops. This should not be in RIB as it has been
    # deleted.
    rib_ipv4_bgp_route1 = dict()
    rib_ipv4_bgp_route1['Route'] = '123.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the BGP
    # route 123.0.0.1/32 and its next-hops. This should not be in FIB as it has
    # been deleted.
    route_ipv4_bgp_route1 = rib_ipv4_bgp_route1

    # Populate the expected RIB ("show rib") route dictionary for the static
    # route 143.0.0.1/32 and its next-hops. This should not be in RIB as it has
    # been deleted.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'

    # Populate the expected RIB ("show rib") route dictionary for the static
    # route 143.0.0.1/32 and its next-hops. This should not be in FIB as it
    # has been deleted.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the BGP route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_bgp_route2 = dict()
    rib_ipv4_bgp_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_bgp_route2['NumberNexthops'] = '1'
    rib_ipv4_bgp_route2['1.1.1.5'] = dict()
    rib_ipv4_bgp_route2['1.1.1.5']['Distance'] = '6'
    rib_ipv4_bgp_route2['1.1.1.5']['Metric'] = '0'
    rib_ipv4_bgp_route2['1.1.1.5']['RouteType'] = 'bgp'

    # Populate the expected FIB ("show ip route") route dictionary for the BGP
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_bgp_route2 = rib_ipv4_bgp_route2
    step("Verifying the IPv4 static and BGP "
         "routes on switch 1 after route deletes")
    # Verify the static/BGP routes in RIB and FIB
    sw1("configure terminal")
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    aux_route = route_ipv4_bgp_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route1)
    aux_route = rib_ipv4_bgp_route1["Route"]
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route1)
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    aux_route = route_ipv4_bgp_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'bgp', route_ipv4_bgp_route2)
    aux_route = rib_ipv4_bgp_route2["Route"]
    verify_show_rib(sw1, aux_route, 'bgp', rib_ipv4_bgp_route2)


@mark.timeout(ZEBRA_DEFAULT_TIMEOUT)
@mark.gate
def test_zebra_ct_ipv4_static_bgp_nexthop_selection(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    sw2 = topology.get("sw2")
    assert sw2 is not None
    add_static_bgp_routes(sw1, sw2, step)
    shutdown_static_bgp_routes_next_hop_interfaces(sw1, sw2, step)
    no_shutdown_static_bgp_routes_next_hop_interfaces(sw1, sw2, step)
    add_nexthop_to_make_bgp_route_ecmp(sw1, sw2, step)
    remove_nexthop_to_make_bgp_route_single(sw1, sw2, step)
    delete_static_bgp_routes(sw1, sw2, step)
