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
# "show ip/ipv6 route/show rib/show running-config".
def add_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    # Enabling interface 1 on sw1
    step("Enabling interface1 on SW1")

    # Interfaces to configure
    sw1_interfaces = []

    # IPs to configure
    sw1_ifs_ips = ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4", "5.5.5.5"]

    # IPv6 addresses to configure
    sw1_ifs_ipv6s = ["111:111::1", "222:222::2", "333:333::3", "444:444::4",
                     "555:555::5"]
    size = len(sw1_ifs_ips)
    # Adding interfaces to configure, 4th and 5th IPs are configured on
    # last interface
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
    step("Configuring switch 1 IPv6 static routes ")

    # Configure IPv6 route 1234:1234::1/128 with 4 ECMP next-hops.
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

    # Configure IPv4 route 2234:2234::1/128 with 1 next-hop.
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

    # Configure IPv4 route 3234:3234::1/128 with 1 next-hop.
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

    # Verify route 123.0.0.1/32 and next-hops in RIB, FIB and
    # running-config
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


# This test does "no routing" trigger on the routed interfaces and checks if
# the routes and next-hops show correctly or deleted correctly in the output
# of "show ip/ipv6 route/show rib/show running-config".
def no_routing_trigger_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("Entering interface for link 1 SW1, to execute 'no routing'")

    # Make the L3 interface 1 as L2 by executing "no routing"
    sw1("interface %s" % sw1_intf1)
    sw1("no routing")
    sw1("exit")

    step("Entering interface for link 4 SW1, to execute 'no routing'")

    # Make the L3 interface 4 as L2 by executing "no routing"
    sw1("interface %s" % sw1_intf4)
    sw1("no routing")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops. The next-hops which were routing via
    # "no routed" interfaces should be removed from the RIB.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '2'
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
    # route 123.0.0.1/32 and its next-hops. The next-hops which were
    # routing via "no routed" interfaces should be removed from the FIB.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 143.0.0.1/32 and its next-hops. The next-hops which were routing via
    # "no routed" interfaces should be removed from the RIB.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops. The next-hops which were
    # routing via "no routed" interfaces should be removed from the FIB.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 163.0.0.1/32 and its next-hops. The next-hops which were routing via
    # "no routed" interfaces should be removed from the RIB.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_intf2] = dict()
    rib_ipv4_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. The next-hops which were
    # routing via "no routed" interfaces should be removed from the FIB.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 1234:1234::1/128 and its next-hops. The next-hops which were routing via
    # "no routed" interfaces should be removed from the RIB.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = '1234:1234::1/128'
    rib_ipv6_static_route1['NumberNexthops'] = '2'
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

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 1234:1234::1/128 and its next-hops. The next-hops which were
    # routing via "no routed" interfaces should be removed from the FIB.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 2234:2234::1/128 and its next-hops. The next-hops which were routing via
    # "no routed" interfaces should be removed from the RIB.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2234:2234::1/128 and its next-hops. The next-hops which were
    # routing via "no routed" interfaces should be removed from the FIB.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 3234:3234::1/128 and its next-hops. The next-hops which were routing via
    # "no routed" interfaces should be removed from the RIB.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'
    rib_ipv6_static_route3['NumberNexthops'] = '1'
    rib_ipv6_static_route3[sw1_intf2] = dict()
    rib_ipv6_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops. The next-hops which were
    # routing via "no routed" interfaces should be removed from the FIB.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    step("Verifying the IPv4 static routes on switch 1")
    # Verify route 123.0.0.1/32 and next-hops in RIB, FIB and
    # running-config. The next-hops which were "no routed" should not
    # appear in running-config.
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
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
    # presence of all next-hops in running-config
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
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
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=False,
                                                 route=aux_route,
                                                 nexthop=sw1_intf4)

    # Verify route 2234:2234::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    aux_route = '2234:2234::1/128'
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=False,
                                                 route=aux_route,
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


# This function tests a corner case of "no routing" when the L3 interface
# does not have an IP/IPv6 address but this interface is L3 since it is the
# part of vrf. In case of "no routing" in this kind of interface, zebra should
# clean-up the DB for the route going via this interface.
def no_routing_on_interface_without_ip(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])

    step("Entering interface for link 1 SW1, to execute 'routing'")

    # Make the L2 interface 1 as L3 by executing "routing"
    sw1("interface %s" % sw1_intf1)
    sw1("routing")
    sw1("exit")

    # Add a static IPv4 route with next-hop interface as 1
    sw1("ip route 203.0.0.1/32 %s" % sw1_intf1)

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 203.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '203.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '1'
    rib_ipv4_static_route1[sw1_intf1] = dict()
    rib_ipv4_static_route1[sw1_intf1]['Distance'] = '1'
    rib_ipv4_static_route1[sw1_intf1]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf1]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 203.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Add a static IPv6 route with next-hop interface as 1
    sw1("ipv6 route 2003:2003::1/128 %s" % sw1_intf1)

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 2003:2003::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = '2003:2003::1/128'
    rib_ipv6_static_route1['NumberNexthops'] = '1'
    rib_ipv6_static_route1[sw1_intf1] = dict()
    rib_ipv6_static_route1[sw1_intf1]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_intf1]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_intf1]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2003:2003::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    step("Verifying the IPv4 static routes on switch 1")

    # Verify route 203.0.0.1/32 and next-hops in RIB, FIB and
    # running-config
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='203.0.0.1/32',
                                             nexthop=sw1_intf1)

    # Verify route 2003:2003::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='2003:2003::1/128',
                                             nexthop=sw1_intf1)

    step("Entering interface for link 1 SW1, to execute 'no routing'")

    # Make the L3 interface 1 as L2 by executing "no routing"
    sw1("interface %s" % sw1_intf1)
    sw1("no routing")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 203.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '203.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 203.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 2003:2003::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = '2003:2003::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2003:2003::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Verify route 203.0.0.1/32 and next-hops in RIB, FIB and
    # running-config
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=True,
                                                 route='203.0.0.1/32',
                                                 nexthop=sw1_intf1)

    # Verify route 2003:2003::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=False,
                                                 route='2003:2003::1/'
                                                 '128',
                                                 nexthop=sw1_intf1)


# This test does "routing" trigger on the non-routed interfaces and checks if
# the routes and next-hops show correctly or not added incorrectly in the
# output of "show ip/ipv6 route/show rib/show running-config".
def routing_trigger_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("Entering interface for link 1 SW1, to execute 'routing'")

    # Make the L2 interface 1 as L3 by executing "routing"
    sw1("interface %s" % sw1_intf1)
    sw1("routing")
    sw1("exit")
    step("Entering interface for link 4 SW1, to execute 'routing'")

    # Make the L2 interface 4 as L3 by executing "routing"
    sw1("interface %s" % sw1_intf4)
    sw1("routing")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops. "Routing" trigger on interfaces should
    # not add any next-hops to the RIB.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '2'
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
    # route 123.0.0.1/32 and its next-hops. "Routing" trigger on interfaces
    # should not add any next-hops to the RIB.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 143.0.0.1/32 and its next-hops. "Routing" trigger on interfaces should
    # not add any next-hops to the RIB.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops. "Routing" trigger on interfaces
    # should not add any next-hops to the RIB.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 163.0.0.1/32 and its next-hops. "Routing" trigger on interfaces should
    # not add any next-hops to the RIB.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_intf2] = dict()
    rib_ipv4_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. "Routing" trigger on interfaces
    # should not add any next-hops to the RIB.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 1234:1234::1/128 and its next-hops. "Routing" trigger on interfaces
    # should not add any next-hops to the RIB.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = '1234:1234::1/128'
    rib_ipv6_static_route1['NumberNexthops'] = '2'
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

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 1234:1234::1/128 and its next-hops. "Routing" trigger on
    # interfaces should not add any next-hops to the RIB.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 2234:2234::1/128 and its next-hops. "Routing" trigger on interfaces
    # should not add any next-hops to the RIB.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2234:2234::1/128 and its next-hops. "Routing" trigger on
    # interfaces should not add any next-hops to the RIB.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 3234:3234::1/128 and its next-hops. "Routing" trigger on interfaces
    # should not add any next-hops to the RIB.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'
    rib_ipv6_static_route3['NumberNexthops'] = '1'
    rib_ipv6_static_route3[sw1_intf2] = dict()
    rib_ipv6_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops. "Routing" trigger on
    # interfaces should not add any next-hops to the RIB.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    step("Verifying the IPv4 static routes on switch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB, FIB and
    # running-config. The next-hops which were "no routed" earlier and
    # now routed should not appear in running-config.
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
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
    route_and_nexthop_in_show_running_config(sw1=sw1,
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
    aux_route = '1234:1234::1/128'
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
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

    # Verify route 3234:3234::1/128 and next-hops in RIB, FIB and
    # running-config. The next-hops which were "no routed" earlier and
    # now routed should not appear in running-config.
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='3234:3234::1/128',
                                             nexthop=sw1_intf2)


# This test case configures few L3 sub-interfaces and adds few IPv4/IPv6
# static routes with sub-interfaces as next-hops.
def add_static_routes_via_l3_sub_interfaces(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf4 = format(sw1.ports["if04"])

    # Add L3 sub-interfaces within interface 1
    sw1("interface %s.1" % sw1_intf1)
    sw1("encapsulation dot1Q 2")
    sw1("ip address 10.10.10.10/24")
    sw1("ipv6 address 100:100::1/64")
    sw1("no shutdown")
    sw1("exit")

    sw1("interface %s.2" % sw1_intf1)
    sw1("encapsulation dot1Q 3")
    sw1("ip address 11.11.11.11/24")
    sw1("ipv6 address 101:101::1/64")
    sw1("no shutdown")
    sw1("exit")

    # Add L3 sub-interfaces within interface 4
    sw1("interface %s.1" % sw1_intf4)
    sw1("encapsulation dot1Q 4")
    sw1("ip address 40.40.40.40/24")
    sw1("ipv6 address 400:400::1/64")
    sw1("no shutdown")
    sw1("exit")

    sw1("interface %s.2" % sw1_intf4)
    sw1("encapsulation dot1Q 5")
    sw1("ip address 41.41.41.41/24")
    sw1("ipv6 address 401:401::1/64")
    sw1("no shutdown")
    sw1("exit")

    # Add IPv4 ECMP static route via the sub-interfaces
    sw1("ip route 173.0.0.1/32 %s.1" % sw1_intf1)
    sw1("ip route 173.0.0.1/32 11.11.11.13")
    sw1("ip route 173.0.0.1/32 41.41.41.43")

    # Add IPv4 non-ECMP static route via the sub-interfaces
    sw1("ip route 183.0.0.1/32 %s.1" % sw1_intf1)

    # Add IPv6 ECMP static route via the sub-interfaces
    sw1("ipv6 route 4234:4234::1/128 %s.1" % sw1_intf1)
    sw1("ipv6 route 4234:4234::1/128 100:100::6")
    sw1("ipv6 route 4234:4234::1/128 %s.1" % sw1_intf4)

    # Add IPv6 non-ECMP static route via the sub-interfaces
    sw1("ipv6 route 5234:5234::1/128 %s.1" % sw1_intf1)

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 173.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '173.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '3'
    rib_ipv4_static_route1['%s.1' % sw1_intf1] = dict()
    rib_ipv4_static_route1['%s.1' % sw1_intf1]['Distance'] = '1'
    rib_ipv4_static_route1['%s.1' % sw1_intf1]['Metric'] = '0'
    rib_ipv4_static_route1['%s.1' % sw1_intf1]['RouteType'] = \
        'static'
    rib_ipv4_static_route1['11.11.11.13'] = dict()
    rib_ipv4_static_route1['11.11.11.13']['Distance'] = '1'
    rib_ipv4_static_route1['11.11.11.13']['Metric'] = '0'
    rib_ipv4_static_route1['11.11.11.13']['RouteType'] = 'static'
    rib_ipv4_static_route1['41.41.41.43'] = dict()
    rib_ipv4_static_route1['41.41.41.43']['Distance'] = '1'
    rib_ipv4_static_route1['41.41.41.43']['Metric'] = '0'
    rib_ipv4_static_route1['41.41.41.43']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 173.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 183.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '183.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['%s.1' % sw1_intf1] = dict()
    rib_ipv4_static_route2['%s.1' % sw1_intf1]['Distance'] = '1'
    rib_ipv4_static_route2['%s.1' % sw1_intf1]['Metric'] = '0'
    rib_ipv4_static_route2['%s.1' % sw1_intf1]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 183.0.0.1/32 and its next-hops.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 4234:4234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = '4234:4234::1/128'
    rib_ipv6_static_route1['NumberNexthops'] = '3'
    rib_ipv6_static_route1['%s.1' % sw1_intf1] = dict()
    rib_ipv6_static_route1['%s.1' % sw1_intf1]['Distance'] = '1'
    rib_ipv6_static_route1['%s.1' % sw1_intf1]['Metric'] = '0'
    rib_ipv6_static_route1['%s.1' % sw1_intf1]['RouteType'] = \
        'static'
    rib_ipv6_static_route1['100:100::6'] = dict()
    rib_ipv6_static_route1['100:100::6']['Distance'] = '1'
    rib_ipv6_static_route1['100:100::6']['Metric'] = '0'
    rib_ipv6_static_route1['100:100::6']['RouteType'] = 'static'
    rib_ipv6_static_route1['%s.1' % sw1_intf4] = dict()
    rib_ipv6_static_route1['%s.1' % sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route1['%s.1' % sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route1['%s.1' % sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 4234:4234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 5234:5234::1/128 and its next-hops.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '5234:5234::1/128'
    rib_ipv6_static_route2['NumberNexthops'] = '1'
    rib_ipv6_static_route2['%s.1' % sw1_intf1] = dict()
    rib_ipv6_static_route2['%s.1' % sw1_intf1]['Distance'] = '1'
    rib_ipv6_static_route2['%s.1' % sw1_intf1]['Metric'] = '0'
    rib_ipv6_static_route2['%s.1' % sw1_intf1]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 5234:5234::1/128 and its next-hops.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    step("Verifying the IPv4 static routes via loopbacks on switch 1")

    # Verify route 173.0.0.1/32 and next-hops in RIB, FIB and
    # running-config
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='173.0.0.1/32',
                                             nexthop=sw1_intf1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='173.0.0.1/32',
                                             nexthop='11.11.11.13')
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='173.0.0.1/32',
                                             nexthop='41.41.41.43')

    # Verify route 183.0.0.1/32 and next-hops in RIB, FIB and
    # running-config
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='183.0.0.1/32',
                                             nexthop=sw1_intf1 + '.1')

    # Verify route 4234:4234::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='4234:4234::1/128',
                                             nexthop=sw1_intf1 + '.1')
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='4234:4234::1/128',
                                             nexthop='100:100::6')
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='4234:4234::1/128',
                                             nexthop=sw1_intf4 + '.1')

    # Verify route 5234:5234::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='5234:5234::1/128',
                                             nexthop=sw1_intf1 + '.1')


# This test case does "no routing" in the parent L3 interface. This parent
# interface contains the L3 sub-interface. "no routing" trigger in the
# parent L3 interface will cause the L3 sub-interface to be deleted. The
# IPv4 and IPv6 static routes and the next-hops routing via those L3
# sub-interfaces should be deleted from DB.
def no_routing_trigger_l3_parent_interfaces(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("Entering interface for link 1 SW1, to execute 'no routing'")

    # Make the L3 interface 1 as L2 by executing "no routing"
    sw1("interface %s" % sw1_intf1)
    sw1("no routing")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 173.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '173.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '1'
    rib_ipv4_static_route1['41.41.41.43'] = dict()
    rib_ipv4_static_route1['41.41.41.43']['Distance'] = '1'
    rib_ipv4_static_route1['41.41.41.43']['Metric'] = '0'
    rib_ipv4_static_route1['41.41.41.43']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 173.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 183.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '183.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 183.0.0.1/32 and its next-hops.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 4234:4234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = '4234:4234::1/128'
    rib_ipv6_static_route1['NumberNexthops'] = '1'
    rib_ipv6_static_route1['%s.1' % sw1_intf4] = dict()
    rib_ipv6_static_route1['%s.1' % sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route1['%s.1' % sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route1['%s.1' % sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 4234:4234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 5234:5234::1/128 and its next-hops.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '5234:5234::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 5234:5234::1/128 and its next-hops.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    step("Verifying the IPv4 static routes via loopbacks on switch 1")

    # Verify route 173.0.0.1/32 and next-hops in RIB, FIB and
    # running-config
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=True,
                                                 route='173.0.0.1/32',
                                                 nexthop=sw1_intf1+'.1')
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=True,
                                                 route='173.0.0.1/32',
                                                 nexthop='11.11.11.13')
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=True,
                                             route='173.0.0.1/32',
                                             nexthop='41.41.41.43')

    # Verify route 183.0.0.1/32 and next-hops in RIB, FIB and
    # running-config
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=True,
                                                 route='183.0.0.1/32',
                                                 nexthop=sw1_intf1+'.1')

    # Verify route 4234:4234::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=False,
                                                 route='4234:4234::1'
                                                 '/128',
                                                 nexthop=sw1_intf1+'.1')
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=False,
                                                 route='4234:4234::1'
                                                 '/128',
                                                 nexthop='100:100::6')
    route_and_nexthop_in_show_running_config(sw1=sw1,
                                             if_ipv4=False,
                                             route='4234:4234::1/128',
                                             nexthop=sw1_intf4 + '.1')

    # Verify route 5234:5234::1/128 and next-hops in RIB, FIB and verify the
    # presence of all next-hops in running-config
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    route_and_nexthop_not_in_show_running_config(sw1=sw1,
                                                 if_ipv4=False,
                                                 route='5234:5234::1'
                                                 '/128',
                                                 nexthop=sw1_intf1+'.1')


@mark.timeout(ZEBRA_DEFAULT_TIMEOUT)
@mark.gate
def test_zebra_ct_no_routing_trigger(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    sw2 = topology.get("sw2")
    assert sw2 is not None
    add_static_routes(sw1, sw2, step)
    no_routing_trigger_static_routes(sw1, sw2, step)
    no_routing_on_interface_without_ip(sw1, sw2, step)
    routing_trigger_static_routes(sw1, sw2, step)
    add_static_routes_via_l3_sub_interfaces(sw1, sw2, step)
    no_routing_trigger_l3_parent_interfaces(sw1, sw2, step)
