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
    route_and_nexthop_in_show_running_config,
    route_and_nexthop_not_in_show_running_config,
    verify_show_ip_route,
    verify_show_ipv6_route,
    verify_show_rib,
    ZEBRA_DEFAULT_TIMEOUT
)
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


# This test configures IPv4 and IPv6 ECMP static routes and checks if the
# routes and next-hops show correctly in the output of
# "show ip route/show rib". The route configuration is also verified in
# the output of "show running-config".
def add_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    # Interfaces to configure
    sw1_interfaces = []

    # IPs to configure
    sw1_ifs_ips = ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4", "5.5.5.5"]

    # IPv6 addresses to configure
    sw1_ifs_ipv6s = ["111:111::1", "222:222::2", "333:333::3", "444:444::4",
                     "555:555::5"]
    size = len(sw1_ifs_ips)

    # Adding interfaces, 4th and 5th IP are configured on the last interface,
    # so the last one is repeated on the array
    for i in range(size):
        if i is not size - 1:
            sw1_interfaces.append(sw1.ports["if0{}".format(i + 1)])
        else:
            sw1_interfaces.append(sw1.ports["if0{}".format(i)])
    sw1_mask = 24
    sw1_ipv6_mask = 64
    step("Configuring interfaces and IPs on SW1")
    sw1("configure terminal")
    for i in range(size):
        sw1("interface {}".format(sw1_interfaces[i]))
        if i is not size - 1:
            sw1("ip address {}/{}".format(sw1_ifs_ips[i], sw1_mask))
            sw1("ipv6 address {}/{}".format(sw1_ifs_ipv6s[i], sw1_ipv6_mask))
        else:
            sw1("ip address {}/{} secondary".format(sw1_ifs_ips[i], sw1_mask))
            sw1("ipv6 address {}/{} secondary".format(sw1_ifs_ipv6s[i],
                                                      sw1_ipv6_mask))
        sw1("no shutdown")
        sw1("exit")
        output = sw1("do show running-config")
        assert "interface {}".format(sw1_interfaces[i]) in output
        assert "ip address {}/{}".format(sw1_ifs_ips[i], sw1_mask) in output
        assert "ipv6 address {}/{}".format(sw1_ifs_ipv6s[i],
                                           sw1_ipv6_mask) in output
    step("Cofiguring sw1 IPV4 static routes")
    # Routes to configure
    nexthops = ["1.1.1.2", sw1_interfaces[1],
                sw1_interfaces[2], "5.5.5.1"]
    for i in range(size - 1):
        sw1("ip route 123.0.0.1/32 {}".format(nexthops[i]))
        output = sw1("do show running-config")
        assert "ip route 123.0.0.1/32 {}".format(nexthops[i]) in output

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '4'
    rib_ipv4_static_route1['1.1.1.2'] = dict()
    rib_ipv4_static_route1['1.1.1.2']['Distance'] = '1'
    rib_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    rib_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    rib_ipv4_static_route1[sw1_intf2] = dict()
    rib_ipv4_static_route1[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv4_static_route1[sw1_intf3] = dict()
    rib_ipv4_static_route1[sw1_intf3]['Distance'] = '1'
    rib_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv4_static_route1['5.5.5.1'] = dict()
    rib_ipv4_static_route1['5.5.5.1']['Distance'] = '1'
    rib_ipv4_static_route1['5.5.5.1']['Metric'] = '0'
    rib_ipv4_static_route1['5.5.5.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Configure IPv4 route 143.0.0.1/32 with 1 next-hop.
    sw1("ip route 143.0.0.1/32 4.4.4.1")
    output = sw1("do show running-config")
    assert "ip route 143.0.0.1/32 4.4.4.1" in output

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

    # Configure IPv4 route 163.0.0.1/32 with 1 next-hop.
    sw1("ip route 163.0.0.1/32 %s" % sw1_intf2)
    output = sw1("do show running-config")
    assert "ip route 163.0.0.1/32 %s" % sw1_intf2 in output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 163.0.0.1/32 and its next-hops.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_intf2] = dict()
    rib_ipv4_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops.
    route_ipv4_static_route3 = rib_ipv4_static_route3
    for i in range(4):
        sw1("ipv6 route 1234:1234::1/128 {}".format(sw1_interfaces[i]))
        output = sw1("do show running-config")
        assert "ipv6 route 1234:1234::1/128 {}".format(sw1_interfaces[i]) in \
            output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 1234:1234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = '1234:1234::1/128'
    rib_ipv6_static_route1['NumberNexthops'] = '4'
    rib_ipv6_static_route1[sw1_intf1] = dict()
    rib_ipv6_static_route1[sw1_intf1]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_intf1]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_intf1]['RouteType'] = \
        'static'
    rib_ipv6_static_route1[sw1_intf2] = dict()
    rib_ipv6_static_route1[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv6_static_route1[sw1_intf3] = dict()
    rib_ipv6_static_route1[sw1_intf3]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv6_static_route1[sw1_intf4] = dict()
    rib_ipv6_static_route1[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 1234:1234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    sw1("ipv6 route 2234:2234::1/128 %s" % sw1_intf4)
    output = sw1("do show running-config")
    assert "ipv6 route 2234:2234::1/128 %s" % sw1_intf4 in output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 2234:2234::1/128 and its next-hops.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'
    rib_ipv6_static_route2['NumberNexthops'] = '1'
    rib_ipv6_static_route2[sw1_intf4] = dict()
    rib_ipv6_static_route2[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route2[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route2[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2234:2234::1/128 and its next-hops.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    sw1("ipv6 route 3234:3234::1/128 %s" % sw1_intf2)
    output = sw1("do show running-config")
    assert "ipv6 route 3234:3234::1/128 %s" % sw1_intf2 in output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'
    rib_ipv6_static_route3['NumberNexthops'] = '1'
    rib_ipv6_static_route3[sw1_intf2] = dict()
    rib_ipv6_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    step("Verifying the IPv4 static routes on switch 1")
    # Verify route 123.0.0.1/32 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='123.0.0.1/32',
                                             nexthop='1.1.1.2')
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='123.0.0.1/32',
                                             nexthop=sw1_intf2)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='123.0.0.1/32',
                                             nexthop=sw1_intf3)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='123.0.0.1/32',
                                             nexthop='5.5.5.1')

    # Verify route 143.0.0.1/32 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='143.0.0.1/32',
                                             nexthop='4.4.4.1')

    # Verify route 163.0.0.1/32 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='163.0.0.1/32',
                                             nexthop=sw1_intf2)

    step("Verifying the IPv6 static routes on switch 1")

    # Verify route 1234:1234::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='1234:1234::1/128',
                                             nexthop=sw1_intf1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='1234:1234::1/128',
                                             nexthop=sw1_intf2)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='1234:1234::1/128',
                                             nexthop=sw1_intf3)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='1234:1234::1/128',
                                             nexthop=sw1_intf4)

    # Verify route 2234:2234::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='2234:2234::1/128',
                                             nexthop=sw1_intf4)

    # Verify route 3234:3234::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='3234:3234::1/128',
                                             nexthop=sw1_intf2)


def delete_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    # Unconfiguring next-hop 5.5.5.1 for route 123.0.0.1/32
    step("Unconfiguring next-hop 5.5.5.1 for route 123.0.0.1/32")
    sw1("no ip route 123.0.0.1/32 5.5.5.1")

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its remaining next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '3'
    rib_ipv4_static_route1['1.1.1.2'] = dict()
    rib_ipv4_static_route1['1.1.1.2']['Distance'] = '1'
    rib_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    rib_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    rib_ipv4_static_route1[sw1_intf2] = dict()
    rib_ipv4_static_route1[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv4_static_route1[sw1_intf3] = dict()
    rib_ipv4_static_route1[sw1_intf3]['Distance'] = '1'
    rib_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its remaining next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Unconfiguring next-hop 4.4.4.1 for route 143.0.0.1/32
    step("Unconfiguring next-hop 4.4.4.1 for route 143.0.0.1/32")
    sw1("no ip route 143.0.0.1/32 4.4.4.1")

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 143.0.0.1/32 and its remaining next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its remaining next-hops.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Unconfiguring next-hop 2 for route 163.0.0.1/32

    step("Unconfiguring next-hop 2 for route 163.0.0.1/32")
    sw1("no ip route 163.0.0.1/32 %s" % sw1_intf2)

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 163.0.0.1/32 and its remaining next-hops.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its remaining next-hops.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    # Unconfiguring next-hop 1 for route 1234:1234::1/128
    step("Unconfiguring next-hop 1 for route 1234:1234::1/128")
    sw1("no ipv6 route 1234:1234::1/128 %s" % sw1_intf1)

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 1234:1234::1/128 and its remaining next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = '1234:1234::1/128'
    rib_ipv6_static_route1['NumberNexthops'] = '3'
    rib_ipv6_static_route1[sw1_intf2] = dict()
    rib_ipv6_static_route1[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv6_static_route1[sw1_intf3] = dict()
    rib_ipv6_static_route1[sw1_intf3]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv6_static_route1[sw1_intf4] = dict()
    rib_ipv6_static_route1[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 1234:1234::1/128 and its remaining next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Unconfiguring next-hop 4 for route 2234:2234::1/128
    step("Unconfiguring next-hop 4 for route 2234:2234::1/128")
    sw1("no ipv6 route 2234:2234::1/128 %s" % sw1_intf4)

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 2234:2234::1/128 and its remaining next-hops.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 2234:2234::1/128 and its remaining next-hops.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    step("Verifying the IPv4 static routes on switch 1")
    # Verify route 123.0.0.1/32 and next-hops in RIB, FIB and verify the
    # presence of active next-hops in running-config and absence of deleted
    # next-hops in running-config
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='123.0.0.1/32',
                                             nexthop='1.1.1.2')
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='123.0.0.1/32',
                                             nexthop=sw1_intf2)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='123.0.0.1/32',
                                             nexthop=sw1_intf3)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=True,
                                                 route='123.0.0.1/32',
                                                 nexthop='5.5.5.1')

    # Verify route 143.0.0.1/32 and next-hops in RIB, FIB and verify the
    # presence of active next-hops in running-config and absence of deleted
    # next-hops in running-config
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=True,
                                                 route='143.0.0.1/32',
                                                 nexthop='4.4.4.1')

    # Verify route 163.0.0.1/32 and next-hops in RIB, FIB and verify
    # the presence of active next-hops in running-config and absence of
    # deleted next-hops in running-config
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=True,
                                                 route='163.0.0.1/32',
                                                 nexthop=sw1_intf2)

    step("Verifying the IPv6 static routes on switch 1")

    # Verify route 1234:1234::1/128 and next-hops in RIB, FIB and verify the
    # presence of active next-hops in running-config and absence of deleted
    # next-hops in running-config
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    aux_route = '1234:1234::1/128'
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=False,
                                                 route=aux_route,
                                                 nexthop=sw1_intf1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='1234:1234::1/128',
                                             nexthop=sw1_intf2)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='1234:1234::1/128',
                                             nexthop=sw1_intf3)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route=aux_route,
                                             nexthop=sw1_intf4)

    # Verify route 2234:2234::1/128 and next-hops in RIB, FIB and verify the
    # presence of active next-hops in running-config and absence of deleted
    # next-hops in running-config
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    aux_route = '2234:2234::1/128'
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=False,
                                                 route=aux_route,
                                                 nexthop=sw1_intf4)


@mark.timeout(ZEBRA_DEFAULT_TIMEOUT)
@mark.gate
def test_zebra_ct_route_nexthop_delete(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    sw2 = topology.get("sw2")
    assert sw2 is not None
    add_static_routes(sw1, sw2, step)
    delete_static_routes(sw1, sw2, step)
