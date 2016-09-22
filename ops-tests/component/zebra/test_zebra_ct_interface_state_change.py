# -*- coding: utf-8 -*-
#
# (c)Copyright 2015-2016 Hewlett Packard Enterprise Development LP
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
# along with GNU Zebra; see the file COPYING. If not, write to the Free
# Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.from re import match
# Topology definition. the topology contains two back to back switches
# having four links between them.


from zebra_routing import (
    verify_show_ip_route,
    verify_show_ipv6_route,
    verify_show_rib,
    ZEBRA_DEFAULT_TIMEOUT
)
from pytest import mark

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
# "show ip/ipv6 route/show rib".
def configure_static_routes(sw1, sw2, step):

    sw1_interfaces = []

    # IPv4 addresses to cnfigure on switch
    sw1_ifs_ips = ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4", "5.5.5.5"]

    # IPv6 addresses to configure on switch
    sw1_ifs_ipv6s = ["111:111::1", "222:222::2", "333:333::3", "444:444::4",
                     "555:555::5"]

    # adding the interfaces to configure on switch, the 4th and 5th IP are
    # configured within the same interface
    size = len(sw1_ifs_ips)
    for i in range(size):
        if i is not size - 1:
            sw1_interfaces.append(format(sw1.ports["if0{}".format(i + 1)]))
        else:
            sw1_interfaces.append(format(sw1.ports["if0{}".format(i)]))
    sw1_mask = 24
    sw1_ipv6_mask = 64

    step("Configuring interfaces and IPs on SW1")

    # COnfiguring interfaces with its respective addresses and enables
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

    # COnfiguring IP routes
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
    rib_ipv4_static_route1[nexthops[1]] = dict()
    rib_ipv4_static_route1[nexthops[1]]['Distance'] = '1'
    rib_ipv4_static_route1[nexthops[1]]['Metric'] = '0'
    rib_ipv4_static_route1[nexthops[1]]['RouteType'] = \
        'static'
    rib_ipv4_static_route1[nexthops[2]] = dict()
    rib_ipv4_static_route1[nexthops[2]]['Distance'] = '1'
    rib_ipv4_static_route1[nexthops[2]]['Metric'] = '0'
    rib_ipv4_static_route1[nexthops[2]]['RouteType'] = \
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
    sw1("ip route 163.0.0.1/32 %s" % sw1_interfaces[1])
    output = sw1("do show running-config")
    assert "ip route 163.0.0.1/32 %s" % sw1_interfaces[1] in output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 163.0.0.1/32 and its next-hops.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_interfaces[1]] = dict()
    rib_ipv4_static_route3[sw1_interfaces[1]]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_interfaces[1]]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_interfaces[1]]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    step("Configuring switch 1IPv6 static routes")

    # Configure IPv6 route 1234:1234::1/128 with 4 ECMP next-hops.
    for i in range(4):
        sw1("ipv6 route 1234:1234::1/128 {}".format(sw1_interfaces[i]))
        output = sw1("do show running-config")
        assert "ipv6 route 1234:1234::1/128 {}".format(
            sw1_interfaces[i]) in output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 1234:1234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = '1234:1234::1/128'
    rib_ipv6_static_route1['NumberNexthops'] = '4'
    rib_ipv6_static_route1[sw1_interfaces[0]] = dict()
    rib_ipv6_static_route1[sw1_interfaces[0]]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_interfaces[0]]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_interfaces[0]]['RouteType'] = \
        'static'
    rib_ipv6_static_route1[sw1_interfaces[1]] = dict()
    rib_ipv6_static_route1[sw1_interfaces[1]]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_interfaces[1]]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_interfaces[1]]['RouteType'] = \
        'static'
    rib_ipv6_static_route1[sw1_interfaces[2]] = dict()
    rib_ipv6_static_route1[sw1_interfaces[2]]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_interfaces[2]]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_interfaces[2]]['RouteType'] = \
        'static'
    rib_ipv6_static_route1[sw1_interfaces[3]] = dict()
    rib_ipv6_static_route1[sw1_interfaces[3]]['Distance'] = '1'
    rib_ipv6_static_route1[sw1_interfaces[3]]['Metric'] = '0'
    rib_ipv6_static_route1[sw1_interfaces[3]]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 1234:1234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Configure IPv6 route 2234:2234::1/128 with 1 next-hop.
    sw1("ipv6 route 2234:2234::1/128 %s" % sw1_interfaces[3])
    output = sw1("do show running-config")
    assert "ipv6 route 2234:2234::1/128 %s" % sw1_interfaces[3] in \
        output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 2234:2234::1/128 and its next-hops.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'
    rib_ipv6_static_route2['NumberNexthops'] = '1'
    rib_ipv6_static_route2[sw1_interfaces[3]] = dict()
    rib_ipv6_static_route2[sw1_interfaces[3]]['Distance'] = '1'
    rib_ipv6_static_route2[sw1_interfaces[3]]['Metric'] = '0'
    rib_ipv6_static_route2[sw1_interfaces[3]]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2234:2234::1/128 and its next-hops.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    # Configure IPv6 route 3234:3234::1/128 with 1 next-hop.
    sw1("ipv6 route 3234:3234::1/128 %s" % sw1_interfaces[1])
    output = sw1("do show running-config")
    assert "ipv6 route 3234:3234::1/128 %s" % sw1_interfaces[1] in \
        output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'
    rib_ipv6_static_route3['NumberNexthops'] = '1'
    rib_ipv6_static_route3[sw1_interfaces[1]] = dict()
    rib_ipv6_static_route3[sw1_interfaces[1]]['Distance'] = '1'
    rib_ipv6_static_route3[sw1_interfaces[1]]['Metric'] = '0'
    rib_ipv6_static_route3[sw1_interfaces[1]]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    step("Verifying the IPv4 static routes onswitch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route 1234:1234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)


# This test shuts down two interfaces and checks if the static routes and
# next-hops show correctly in the output of "show ip/ipv6 route/show rib".
def interface_shut_trigger_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    # Shutting interface 2 on sw1
    step("shutting interface2 on SW1")
    sw1("interface %s" % sw1_intf2)
    sw1("shutdown")
    sw1("exit")

    # Shutting interface 4 on sw1
    step("shutting interface4 on SW1")
    sw1("interface %s" % sw1_intf4)
    sw1("shutdown")
    sw1("exit")

    # Add a new IPv4 static route 193.0.0.1/32 via interface 4
    step("Add a ipv4 static route via shut interface4 on SW1")
    sw1("ip route 193.0.0.1/32 {}".format(sw1.ports["if04"]))
    output = sw1("do show running-config")
    assert "ip route 193.0.0.1/32 {}".format(sw1.ports["if04"]) in output

    # Add a new IPv6 static route 4234:4234::1/128 via interface 4
    step("Add a ipv6 static route via shut interface4 on SW1")
    sw1("ipv6 route 4234:4234::1/128 {}".format(sw1.ports["if04"]))
    output = sw1("do show running-config")
    assert "ipv6 route 4234:4234::1/128 {}".format(sw1.ports["if04"]) in output

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops. The next-hops via interfaces 2 and
    # 4 should be withdrawn from FIB.
    route_ipv4_static_route1 = dict()
    route_ipv4_static_route1['Route'] = '123.0.0.1/32'
    route_ipv4_static_route1['NumberNexthops'] = '2'
    route_ipv4_static_route1['1.1.1.2'] = dict()
    route_ipv4_static_route1['1.1.1.2']['Distance'] = '1'
    route_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    route_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    route_ipv4_static_route1[sw1_intf3] = dict()
    route_ipv4_static_route1[sw1_intf3]['Distance'] = '1'
    route_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    route_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops. All four next-hops of the route should
    # be maintained in the RIB.
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
    # route 143.0.0.1/32 and its next-hops. The next-hop for the route
    # should be withdrawn from the FIB.
    route_ipv4_static_route2 = dict()
    route_ipv4_static_route2['Route'] = '143.0.0.1/32'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 143.0.0.1/32 and its next-hops. The next-hop for the route
    # should be maintained in the RIB.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. The next-hop for the route
    # should be withdrawn from the FIB.
    route_ipv4_static_route3 = dict()
    route_ipv4_static_route3['Route'] = '163.0.0.1/32'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. The next-hop for the route
    # should be maintained in the RIB.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_intf2] = dict()
    rib_ipv4_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 193.0.0.1/32 and its next-hops. The next-hop for the route
    # should not be programmed into the FIB.
    route_ipv4_static_route4 = dict()
    route_ipv4_static_route4['Route'] = '193.0.0.1/32'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 193.0.0.1/32 and its next-hops. The next-hop for the route
    # should be maintained in the RIB.
    rib_ipv4_static_route4 = dict()
    rib_ipv4_static_route4['Route'] = '193.0.0.1/32'
    rib_ipv4_static_route4['NumberNexthops'] = '1'
    rib_ipv4_static_route4[sw1_intf4] = dict()
    rib_ipv4_static_route4[sw1_intf4]['Distance'] = '1'
    rib_ipv4_static_route4[sw1_intf4]['Metric'] = '0'
    rib_ipv4_static_route4[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 1234:1234::1/128 and its next-hops. The next-hops via interfaces 2
    # and 4 should be withdrawn from FIB.
    route_ipv6_static_route1 = dict()
    route_ipv6_static_route1['Route'] = '1234:1234::1/128'
    route_ipv6_static_route1['NumberNexthops'] = '2'
    route_ipv6_static_route1[sw1_intf1] = dict()
    route_ipv6_static_route1[sw1_intf1]['Distance'] = '1'
    route_ipv6_static_route1[sw1_intf1]['Metric'] = '0'
    route_ipv6_static_route1[sw1_intf1]['RouteType'] = \
        'static'
    route_ipv6_static_route1[sw1_intf3] = dict()
    route_ipv6_static_route1[sw1_intf3]['Distance'] = '1'
    route_ipv6_static_route1[sw1_intf3]['Metric'] = '0'
    route_ipv6_static_route1[sw1_intf3]['RouteType'] = \
        'static'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 1234:1234::1/128 and its next-hops. All four next-hops of the route
    # should be maintained in the RIB.
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
    # route 2234:2234::1/128 and its next-hops. The next-hops via interfaces 2
    # and 4 should be withdrawn from FIB.
    route_ipv6_static_route2 = dict()
    route_ipv6_static_route2['Route'] = '2234:2234::1/128'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 2234:2234::1/128 and its next-hops. the next-hops of the route
    # should be maintained in the RIB.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'
    rib_ipv6_static_route2['NumberNexthops'] = '1'
    rib_ipv6_static_route2[sw1_intf4] = dict()
    rib_ipv6_static_route2[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route2[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route2[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops. The next-hops via interfaces 2
    # and 4 should be withdrawn from FIB.
    route_ipv6_static_route3 = dict()
    route_ipv6_static_route3['Route'] = '3234:3234::1/128'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 3234:3234::1/128 and its next-hops. the next-hops of the route
    # should be maintained in the RIB.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'
    rib_ipv6_static_route3['NumberNexthops'] = '1'
    rib_ipv6_static_route3[sw1_intf2] = dict()
    rib_ipv6_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 4234:4234::1/128 and its next-hops. The next-hops via interfaces 2
    # and 4 should not be added into the FIB.
    route_ipv6_static_route4 = dict()
    route_ipv6_static_route4['Route'] = '4234:4234::1/128'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 4234:4234::1/128 and its next-hops. the next-hops of the route
    # should be maintained in the RIB.
    rib_ipv6_static_route4 = dict()
    rib_ipv6_static_route4['Route'] = '4234:4234::1/128'
    rib_ipv6_static_route4['NumberNexthops'] = '1'
    rib_ipv6_static_route4[sw1_intf4] = dict()
    rib_ipv6_static_route4[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route4[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route4[sw1_intf4]['RouteType'] = \
        'static'

    step("Verifying the IPv4 static routes on"
         "switch 1 after interface shut triggers")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)

    # Verify route 193.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route4["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route4)
    aux_route = rib_ipv4_static_route4["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route4)

    step("Verifying the IPv6 static routes on"
         "switch 1 after interface shut triggers")

    # Verify route 1234:1234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)

    # Verify route 4234:4234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route4["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route4)
    aux_route = rib_ipv6_static_route4["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route4)


def interface_no_shut_trigger_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    # Un-Shutting interface 2 on sw1
    step("un-shutting interface2 on SW1")
    sw1("interface %s" % sw1_intf2)
    sw1("no shutdown")
    sw1("exit")

    # Un-Shutting interface 4 on sw1
    step("un-shutting interface4 on SW1")
    sw1("interface %s" % sw1_intf4)
    sw1("no shutdown")
    sw1("exit")

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
    # route 123.0.0.1/32 and its next-hops. The next-hops via interfaces
    # 2 and 4 should now be present in the FIB.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 143.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops. The next-hops via interfaces
    # 2 and 4 should now be present in the FIB.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 163.0.0.1/32 and its next-hops.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_intf2] = dict()
    rib_ipv4_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. The next-hops via interfaces
    # 2 and 4 should now be present in the FIB.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 193.0.0.1/32 and its next-hops.
    rib_ipv4_static_route4 = dict()
    rib_ipv4_static_route4['Route'] = '193.0.0.1/32'
    rib_ipv4_static_route4['NumberNexthops'] = '1'
    rib_ipv4_static_route4[sw1_intf4] = dict()
    rib_ipv4_static_route4[sw1_intf4]['Distance'] = '1'
    rib_ipv4_static_route4[sw1_intf4]['Metric'] = '0'
    rib_ipv4_static_route4[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 193.0.0.1/32 and its next-hops. The next-hops via interfaces
    # 2 and 4 should now be present in the FIB.
    route_ipv4_static_route4 = rib_ipv4_static_route4

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
    # route 1234:1234::1/128 and its next-hops. The next-hops via interfaces
    # 2 and 4 should now be present in the FIB.
    route_ipv6_static_route1 = rib_ipv6_static_route1

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
    # route 2234:2234::1/128 and its next-hops. The next-hops via interfaces
    # 2 and 4 should now be present in the FIB.
    route_ipv6_static_route2 = rib_ipv6_static_route2

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
    # route 3234:3234::1/128 and its next-hops. The next-hops via interfaces
    # 2 and 4 should now be present in the FIB.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 4234:4234::1/128 and its next-hops.
    rib_ipv6_static_route4 = dict()
    rib_ipv6_static_route4['Route'] = '4234:4234::1/128'
    rib_ipv6_static_route4['NumberNexthops'] = '1'
    rib_ipv6_static_route4[sw1_intf4] = dict()
    rib_ipv6_static_route4[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route4[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route4[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 4234:4234::1/128 and its next-hops. The next-hops via interfaces
    # 2 and 4 should now be present in the FIB.
    route_ipv6_static_route4 = rib_ipv6_static_route4

    step("Verifying the IPv4 static routes on"
         "switch 1 after interface shut triggers")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)

    # Verify route 193.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route4["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route4)
    aux_route = rib_ipv4_static_route4["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route4)

    step("Verifying the IPv6 static routes on"
         "switch 1 after interface shut triggers")

    # Verify route 1234:1234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)

    # Verify route 4234:4234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route4["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route4)
    aux_route = rib_ipv6_static_route4["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route4)


def interface_unconfiguring_addresses_trigger_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    # interfaces to unconfigure
    sw1_interfaces = [sw1.ports["if01"], sw1.ports["if04"]]
    # IPs to unconfigure
    sw1_ifs_ips = ["1.1.1.1", "5.5.5.5"]
    # IPv6 addresses to unconfigure
    sw1_ifs_ipv6s = ["111:111::1", "555:555::5"]
    size = len(sw1_ifs_ips)
    sw1_mask = 24
    sw1_ipv6_mask = 64

    step("Unconfiguring interfaces and IPs on SW1")
    for i in range(size):
        sw1("interface {}".format(sw1_interfaces[i]))
        if i is not 1:
            sw1("no ip address {}/{}".format(sw1_ifs_ips[i], sw1_mask))
            sw1("no ipv6 address {}/{}".format(sw1_ifs_ipv6s[i],
                                               sw1_ipv6_mask))
        else:
            sw1("no ip address {}/{} secondary".format(sw1_ifs_ips[i],
                                                       sw1_mask))
            sw1("no ipv6 address {}/{} secondary".format(sw1_ifs_ipv6s[i],
                                                         sw1_ipv6_mask))
        sw1("exit")
        output = sw1("do show running-config")
        assert not "ip address {}/{}".format(sw1_ifs_ips[i],
                                             sw1_mask) in output
        assert not "ipv6 address {}/{}".format(sw1_ifs_ipv6s[i],
                                               sw1_ipv6_mask) in output

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops. The next-hops via IP addresses
    # interfaces 1 and 4  should be withdrawn from FIB.
    route_ipv4_static_route1 = dict()
    route_ipv4_static_route1['Route'] = '123.0.0.1/32'
    route_ipv4_static_route1['NumberNexthops'] = '2'
    route_ipv4_static_route1[sw1_intf2] = dict()
    route_ipv4_static_route1[sw1_intf2]['Distance'] = '1'
    route_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    route_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    route_ipv4_static_route1[sw1_intf3] = dict()
    route_ipv4_static_route1[sw1_intf3]['Distance'] = '1'
    route_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    route_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops. All four next-hops of the route should
    # be maintained in the RIB.
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

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 143.0.0.1/32 and its next-hops. The next-hops of the route should
    # be maintained in the RIB.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops. The next-hops via IP addresses
    # interfaces 1 and 4  should be withdrawn from FIB.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 163.0.0.1/32 and its next-hops. The next-hops of the route should
    # be maintained in the RIB.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_intf2] = dict()
    rib_ipv4_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. The next-hops via IP addresses
    # interfaces 1 and 4  should be withdrawn from FIB.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 1234:1234::1/128 and its next-hops. The next-hops of the route
    # should be maintained in the RIB.
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
    # route 1234:1234::1/128 and its next-hops. The next-hops via IPv6
    # addresses interfaces 1 and 4  should be withdrawn from FIB.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 2234:2234::1/128 and its next-hops. The next-hops of the route
    # should be maintained in the RIB.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'
    rib_ipv6_static_route2['NumberNexthops'] = '1'
    rib_ipv6_static_route2[sw1_intf4] = dict()
    rib_ipv6_static_route2[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route2[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route2[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2234:2234::1/128 and its next-hops. The next-hops via IPv6
    # addresses interfaces 1 and 4  should be withdrawn from FIB.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 3234:3234::1/128 and its next-hops. The next-hops of the route
    # should be maintained in the RIB.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'
    rib_ipv6_static_route3['NumberNexthops'] = '1'
    rib_ipv6_static_route3[sw1_intf2] = dict()
    rib_ipv6_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops. The next-hops via IPv6
    # addresses interfaces 1 and 4  should be withdrawn from FIB.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    step("Verifying the IPv4 static routes onswitch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route 1234:1234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)


def interface_configuring_addresses_trigger_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    # Interfaces to configure
    sw1_interfaces = [sw1.ports["if01"], sw1.ports["if04"]]
    # IPs to configure
    sw1_ifs_ips = ["1.1.1.1", "5.5.5.5"]
    # APv6 addresses to confgure
    sw1_ifs_ipv6s = ["111:111::1", "555:555::5"]
    size = len(sw1_ifs_ips)
    sw1_mask = 24
    sw1_ipv6_mask = 64

    step("Configuring interfaces and IPs on SW1")
    for i in range(size):
        sw1("interface {}".format(sw1_interfaces[i]))
        if i is not 1:
            sw1("ip address {}/{}".format(sw1_ifs_ips[i], sw1_mask))
            sw1("ipv6 address {}/{}".format(sw1_ifs_ipv6s[i],
                                            sw1_ipv6_mask))
        else:
            sw1("ip address {}/{} secondary".format(sw1_ifs_ips[i], sw1_mask))
            sw1("ipv6 address {}/{} secondary".format(sw1_ifs_ipv6s[i],
                                                      sw1_ipv6_mask))
        sw1("exit")
        output = sw1("do show running-config")
        assert "ip address {}/{}".format(sw1_ifs_ips[i],
                                         sw1_mask) in output
        assert "ipv6 address {}/{}".format(sw1_ifs_ipv6s[i],
                                           sw1_ipv6_mask) in output

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops. All four next-hops of the route should
    # be maintained in the RIB.
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
    # route 123.0.0.1/32 and its next-hops. The next-hops via IP addresses
    # interfaces 1 and 4  should be reprogrammed into FIB.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 143.0.0.1/32 and its next-hops. The next-hops of the route should
    # be maintained in the RIB.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops. The next-hops via IP addresses
    # interfaces 1 and 4  should be reprogrammed into FIB.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 163.0.0.1/32 and its next-hops. The next-hops of the route should
    # be maintained in the RIB.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_intf2] = dict()
    rib_ipv4_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. The next-hops via IP addresses
    # interfaces 1 and 4  should be reprogrammed into FIB.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 1234:1234::1/128 and its next-hops. The next-hops of the route should
    # be maintained in the RIB.
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
    # route 1234:1234::1/128 and its next-hops. The next-hops via IPv6
    # addresses interfaces 1 and 4  should be reprogrammed into FIB.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 2234:2234::1/128 and its next-hops. The next-hops of the route should
    # be maintained in the RIB.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'
    rib_ipv6_static_route2['NumberNexthops'] = '1'
    rib_ipv6_static_route2[sw1_intf4] = dict()
    rib_ipv6_static_route2[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route2[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route2[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2234:2234::1/128 and its next-hops. The next-hops via IPv6
    # addresses interfaces 1 and 4  should be reprogrammed into FIB.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 3234:3234::1/128 and its next-hops. The next-hops of the route should
    # be maintained in the RIB.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'
    rib_ipv6_static_route3['NumberNexthops'] = '1'
    rib_ipv6_static_route3[sw1_intf2] = dict()
    rib_ipv6_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops. The next-hops via IPv6
    # addresses interfaces 1 and 4  should be reprogrammed into FIB.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    step("Verifying the IPv4 static routes onswitch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route 1234:1234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)


# This test changes the interface addresses and checks if the static
# routes and next-hops show correctly in the output of
# "show ip/ipv6 route/show rib".
def interface_changing_addresses_trigger_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("Entering interface for link 1 and 4 on SW1,"
         " changing an ip/ip6 address")

    # Interfaces to configure
    sw1_interfaces = [sw1.ports["if01"], sw1.ports["if04"]]

    # IPs to configure
    sw1_ifs_ips = ["8.8.8.8", "6.6.6.6"]

    # IPv6 addresses to configure
    sw1_ifs_ipv6s = ["888:888::8", "666:666::6"]

    size = len(sw1_ifs_ips)
    sw1_mask = 24
    sw1_ipv6_mask = 64

    step("Configuring interfaces and IPs on SW1")
    for i in range(size):
        sw1("interface {}".format(sw1_interfaces[i]))
        sw1("ip address {}/{}".format(sw1_ifs_ips[i], sw1_mask))
        sw1("ipv6 address {}/{}".format(sw1_ifs_ipv6s[i], sw1_ipv6_mask))
        sw1("exit")
        output = sw1("do show running-config")
        assert "ip address {}/{}".format(sw1_ifs_ips[i],
                                         sw1_mask) in output
        assert "ipv6 address {}/{}".format(sw1_ifs_ipv6s[i],
                                           sw1_ipv6_mask) in output

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops. All four next-hops of the route should
    # be maintained in the RIB.
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
    # route 123.0.0.1/32 and its next-hops. The next-hops via IP addresses,
    # if the next-hops do not occur in subnets on interfaces 1 and 4,
    # should be withdrawn from FIB.
    route_ipv4_static_route1 = dict()
    route_ipv4_static_route1['Route'] = '123.0.0.1/32'
    route_ipv4_static_route1['NumberNexthops'] = '3'
    route_ipv4_static_route1[sw1_intf2] = dict()
    route_ipv4_static_route1[sw1_intf2]['Distance'] = '1'
    route_ipv4_static_route1[sw1_intf2]['Metric'] = '0'
    route_ipv4_static_route1[sw1_intf2]['RouteType'] = \
        'static'
    route_ipv4_static_route1[sw1_intf3] = dict()
    route_ipv4_static_route1[sw1_intf3]['Distance'] = '1'
    route_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    route_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    route_ipv4_static_route1['5.5.5.1'] = dict()
    route_ipv4_static_route1['5.5.5.1']['Distance'] = '1'
    route_ipv4_static_route1['5.5.5.1']['Metric'] = '0'
    route_ipv4_static_route1['5.5.5.1']['RouteType'] = 'static'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 143.0.0.1/32 and its next-hops. All four next-hops of the route should
    # be maintained in the RIB.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops. The next-hops via IP addresses,
    # if the next-hops do not occur in subnets on interfaces 1 and 4,
    # should be withdrawn from FIB.
    route_ipv4_static_route2 = dict()
    route_ipv4_static_route2['Route'] = '143.0.0.1/32'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 163.0.0.1/32 and its next-hops. All four next-hops of the route should
    # be maintained in the RIB.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_intf2] = dict()
    rib_ipv4_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. The next-hops via IP addresses,
    # if the next-hops do not occur in subnets on interfaces 1 and 4,
    # should be withdrawn from FIB.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 1234:1234::1/128 and its next-hops. All four next-hops of the route
    # should be maintained in the RIB.
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

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 1234:1234::1/128  and its next-hops. The next-hops via IPv6
    # addresses, if the next-hops do not occur in subnets on interfaces 1
    # and 4, should be withdrawn from FIB.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 2234:2234::1/128 and its next-hops. All four next-hops of the route
    # should be maintained in the RIB.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'
    rib_ipv6_static_route2['NumberNexthops'] = '1'
    rib_ipv6_static_route2[sw1_intf4] = dict()
    rib_ipv6_static_route2[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route2[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route2[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 2234:2234::1/128  and its next-hops. The next-hops via IPv6
    # addresses, if the next-hops do not occur in subnets on interfaces 1
    # and 4, should be withdrawn from FIB.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 3234:3234::1/128 and its next-hops. All four next-hops of the route
    # should be maintained in the RIB.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'
    rib_ipv6_static_route3['NumberNexthops'] = '1'
    rib_ipv6_static_route3[sw1_intf2] = dict()
    rib_ipv6_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 3234:3234::1/128  and its next-hops. The next-hops via IPv6
    # addresses, if the next-hops do not occur in subnets on interfaces 1
    # and 4, should be withdrawn from FIB.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    step("Verifying the IPv4 static routes onswitch 1 after changing"
         " interface addresses triggers")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route 1234:1234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)


# This test changes the interface addresses back to the original addresses
# and checks if the static routes and next-hops show correctly in the output
# of "show ip/ipv6 route/show rib".
def interface_changing_back_addresses_trigger_static_routes(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("Entering interface for link 1 and 4 on SW1,"
         " changing back an ip/ip6 address")

    # Interfaces to configure
    sw1_interfaces = [sw1.ports["if01"], sw1.ports["if04"]]

    # IPs to configure
    sw1_ifs_ips = ["1.1.1.1", "4.4.4.4"]

    # IPv6 addresses to configure
    sw1_ifs_ipv6s = ["111:111::1", "444:444::4"]

    size = len(sw1_ifs_ips)
    sw1_mask = 24
    sw1_ipv6_mask = 64

    step("Configuring interfaces and IPs on SW1")
    for i in range(size):
        sw1("interface {}".format(sw1_interfaces[i]))
        sw1("ip address {}/{}".format(sw1_ifs_ips[i], sw1_mask))
        sw1("ipv6 address {}/{}".format(sw1_ifs_ipv6s[i], sw1_ipv6_mask))
        sw1("exit")
        output = sw1("do show running-config")
        assert "ip address {}/{}".format(sw1_ifs_ips[i],
                                         sw1_mask) in output
        assert "ipv6 address {}/{}".format(sw1_ifs_ipv6s[i],
                                           sw1_ipv6_mask) in output

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops. All four next-hops of the route should
    # be maintained in the RIB.
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
    # route 123.0.0.1/32 and its next-hops. The next-hops via IP addresses,
    # if the next-hops occur in subnets on interfaces 1 and 4, should be
    # reprogrammed in FIB.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 143.0.0.1/32 and its next-hops. All four next-hops of the route should
    # be maintained in the RIB.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'
    rib_ipv4_static_route2['NumberNexthops'] = '1'
    rib_ipv4_static_route2['4.4.4.1'] = dict()
    rib_ipv4_static_route2['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route2['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route2['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops. The next-hops via IP addresses,
    # if the next-hops occur in subnets on interfaces 1 and 4, should be
    # reprogrammed in FIB.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 163.0.0.1/32 and its next-hops. All four next-hops of the route should
    # be maintained in the RIB.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'
    rib_ipv4_static_route3['NumberNexthops'] = '1'
    rib_ipv4_static_route3[sw1_intf2] = dict()
    rib_ipv4_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. The next-hops via IP addresses,
    # if the next-hops occur in subnets on interfaces 1 and 4, should be
    # reprogrammed in FIB.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 1234:1234::1/128 and its next-hops. All four next-hops of the route
    # should be maintained in the RIB.
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
    # route 1234:1234::1/128 and its next-hops. The next-hops via IPv6
    # addresses, if the next-hops occur in subnets on interfaces 1 and 4,
    # should be reprogrammed in FIB.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 2234:2234::1/128 and its next-hops. All four next-hops of the route
    # should be maintained in the RIB.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'
    rib_ipv6_static_route2['NumberNexthops'] = '1'
    rib_ipv6_static_route2[sw1_intf4] = dict()
    rib_ipv6_static_route2[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route2[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route2[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2234:2234::1/128 and its next-hops. The next-hops via IPv6
    # addresses, if the next-hops occur in subnets on interfaces 1 and 4,
    # should be reprogrammed in FIB.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 3234:3234::1/128 and its next-hops. All four next-hops of the route
    # should be maintained in the RIB.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'
    rib_ipv6_static_route3['NumberNexthops'] = '1'
    rib_ipv6_static_route3[sw1_intf2] = dict()
    rib_ipv6_static_route3[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route3[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route3[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops. The next-hops via IPv6
    # addresses, if the next-hops occur in subnets on interfaces 1 and 4,
    # should be reprogrammed in FIB.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    step("Verifying the IPv4 static routes onswitch 1 after changing back"
         " interface addresses triggers")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route 1234:1234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)


# This test case adds an inactive next-hop to a route whose next-hop
# is in FIB. The new next-hop should not appear in the output of
# "show ip route" but should appear in "show rib" output.
def add_inactive_nexthop_to_static_routes(sw1, sw2, step):

    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf4 = format(sw1.ports["if04"])

    # Shutting interface 4 on sw1
    step("shutting interface4 on SW1")
    sw1("interface %s" % sw1_intf4)
    sw1("shutdown")
    sw1("exit")

    # Add nexthop 4.4.4.7 to route 163.0.0.1/32
    sw1("ip route 163.0.0.1/32 4.4.4.7")
    output = sw1("do show running-config")
    assert "ip route 163.0.0.1/32 4.4.4.7" in output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 163.0.0.1/32 and its next-hops.
    rib_ipv4_static_route = dict()
    rib_ipv4_static_route['Route'] = '163.0.0.1' + '/' + '32'
    rib_ipv4_static_route['NumberNexthops'] = '2'
    rib_ipv4_static_route[sw1_intf2] = dict()
    rib_ipv4_static_route[sw1_intf2]['Distance'] = '1'
    rib_ipv4_static_route[sw1_intf2]['Metric'] = '0'
    rib_ipv4_static_route[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv4_static_route['4.4.4.7'] = dict()
    rib_ipv4_static_route['4.4.4.7']['Distance'] = '1'
    rib_ipv4_static_route['4.4.4.7']['Metric'] = '0'
    rib_ipv4_static_route['4.4.4.7']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops.
    route_ipv4_static_route = dict()
    route_ipv4_static_route['Route'] = '163.0.0.1' + '/' + '32'
    route_ipv4_static_route['NumberNexthops'] = '1'
    route_ipv4_static_route[sw1_intf2] = dict()
    route_ipv4_static_route[sw1_intf2]['Distance'] = '1'
    route_ipv4_static_route[sw1_intf2]['Metric'] = '0'
    route_ipv4_static_route[sw1_intf2]['RouteType'] = \
        'static'

    # Configure IPv6 route 3234:3234::1/128 with interface 4 as next-hop
    sw1("ipv6 route 3234:3234::1/128 {}".format(sw1.ports["if04"]))
    output = sw1("do show running-config")
    assert "ipv6 route 3234:3234::1/128 {}".format(sw1.ports["if04"]) in output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    rib_ipv6_static_route = dict()
    rib_ipv6_static_route['Route'] = '3234:3234::1' + '/' + '128'
    rib_ipv6_static_route['NumberNexthops'] = '2'
    rib_ipv6_static_route[sw1_intf2] = dict()
    rib_ipv6_static_route[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route[sw1_intf2]['RouteType'] = \
        'static'
    rib_ipv6_static_route[sw1_intf4] = dict()
    rib_ipv6_static_route[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    route_ipv6_static_route = dict()
    route_ipv6_static_route['Route'] = '3234:3234::1' + '/' + '128'
    route_ipv6_static_route['NumberNexthops'] = '1'
    route_ipv6_static_route[sw1_intf2] = dict()
    route_ipv6_static_route[sw1_intf2]['Distance'] = '1'
    route_ipv6_static_route[sw1_intf2]['Metric'] = '0'
    route_ipv6_static_route[sw1_intf2]['RouteType'] = \
        'static'

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route)
    aux_route = rib_ipv4_static_route["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route)

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route)
    aux_route = rib_ipv6_static_route["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route)


# This test case removes an active next-hop from a route which already
# has another inactive next-hop. The route should not exist in the output
# of "show ip route" but should appear in "show rib" output.
def remove_active_nexthop_from_static_routes(sw1, sw2, step):

    sw1_intf4 = format(sw1.ports["if04"])

    # Remove nexthop interface 2 from route 163.0.0.1/32
    sw1("no ip route 163.0.0.1/32 {}".format(sw1.ports["if02"]))
    output = sw1("do show running-config")
    assert "ip route 163.0.0.1/32 {}".format(sw1.ports["if02"]) not in output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 163.0.0.1/32 and its next-hops.
    rib_ipv4_static_route = dict()
    rib_ipv4_static_route['Route'] = '163.0.0.1' + '/' + '32'
    rib_ipv4_static_route['NumberNexthops'] = '1'
    rib_ipv4_static_route['4.4.4.7'] = dict()
    rib_ipv4_static_route['4.4.4.7']['Distance'] = '1'
    rib_ipv4_static_route['4.4.4.7']['Metric'] = '0'
    rib_ipv4_static_route['4.4.4.7']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops. The next-hop for the route
    # should be withdrawn from the FIB.
    route_ipv4_static_route = dict()
    route_ipv4_static_route['Route'] = '163.0.0.1' + '/' + '32'

    # Un-Configure IPv6 route 3234:3234::1/128 with interface 2 as next-hop
    sw1("no ipv6 route 3234:3234::1/128 {}".format(sw1.ports["if02"]))
    output = sw1("do show running-config")
    assert "ipv6 route 3234:3234::1/128 {}".format(sw1.ports["if02"]) not in \
        output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    rib_ipv6_static_route = dict()
    rib_ipv6_static_route['Route'] = '3234:3234::1' + '/' + '128'
    rib_ipv6_static_route['NumberNexthops'] = '1'
    rib_ipv6_static_route[sw1_intf4] = dict()
    rib_ipv6_static_route[sw1_intf4]['Distance'] = '1'
    rib_ipv6_static_route[sw1_intf4]['Metric'] = '0'
    rib_ipv6_static_route[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops. The next-hop for the route
    # should be withdrawn from the FIB.
    route_ipv6_static_route = dict()
    route_ipv6_static_route['Route'] = '3234:3234::1' + '/' + '128'

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route)
    aux_route = rib_ipv4_static_route["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route)

    step("Verification of route 163.0.0.1/32 "
         "after removing active next-hop passed")

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route)
    aux_route = rib_ipv6_static_route["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route)


@mark.timeout(ZEBRA_DEFAULT_TIMEOUT)
@mark.gate
def test_zebra_ct_interface_state_change(topology, step):
    sw1 = topology.get("sw1")
    sw2 = topology.get("sw2")

    assert sw1 is not None
    assert sw2 is not None

    configure_static_routes(sw1, sw2, step)
    interface_shut_trigger_static_routes(sw1, sw2, step)
    interface_no_shut_trigger_static_routes(sw1, sw2, step)
    interface_unconfiguring_addresses_trigger_static_routes(sw1, sw2, step)
    interface_configuring_addresses_trigger_static_routes(sw1, sw2, step)
    interface_changing_addresses_trigger_static_routes(sw1, sw2, step)
    interface_changing_back_addresses_trigger_static_routes(sw1, sw2, step)
    add_inactive_nexthop_to_static_routes(sw1, sw2, step)
    remove_active_nexthop_from_static_routes(sw1, sw2, step)
