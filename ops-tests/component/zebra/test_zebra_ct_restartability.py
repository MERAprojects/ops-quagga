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
    verify_route_in_show_kernel_route,
    ZEBRA_DEFAULT_TIMEOUT,
    ZEBRA_TEST_SLEEP_TIME
)

from time import sleep
from pytest import mark


zebra_stop_command_string = "systemctl stop ops-zebra"
zebra_start_command_string = "systemctl start ops-zebra"


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

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

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
            sw1_interfaces.append(sw1.ports["if0{}".format(i + 1)])
        else:
            sw1_interfaces.append(sw1.ports["if0{}".format(i)])
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
                sw1_interfaces[2], "4.4.4.1"]

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
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route 123.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route1 = dict()
    route_ipv4_kernel_route1['Route'] = '123.0.0.1' + '/' + '32'
    route_ipv4_kernel_route1['NumberNexthops'] = '4'
    route_ipv4_kernel_route1['1.1.1.2'] = dict()
    route_ipv4_kernel_route1['1.1.1.2']['Distance'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['Metric'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['RouteType'] = 'zebra'
    route_ipv4_kernel_route1[sw1_intf2] = dict()
    route_ipv4_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1[sw1_intf3] = dict()
    route_ipv4_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1['4.4.4.1'] = dict()
    route_ipv4_kernel_route1['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 143.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route2 = dict()
    route_ipv4_kernel_route2['Route'] = '143.0.0.1' + '/' + '32'
    route_ipv4_kernel_route2['NumberNexthops'] = '1'
    route_ipv4_kernel_route2['4.4.4.1'] = dict()
    route_ipv4_kernel_route2['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route3 = dict()
    route_ipv4_kernel_route3['Route'] = '163.0.0.1' + '/' + '32'
    route_ipv4_kernel_route3['NumberNexthops'] = '1'
    route_ipv4_kernel_route3[sw1_intf2] = dict()
    route_ipv4_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    step("Configuring switch 1IPv6 static routes")

    # Configure IPv6 route a234:a234::1/128 with 4 ECMP next-hops.
    for i in range(4):
        sw1("ipv6 route a234:a234::1/128 {}".format(sw1_interfaces[i]))
        output = sw1("do show running-config")
        assert "ipv6 route a234:a234::1/128 {}".format(sw1_interfaces[i]) in \
            output

    # Populate the expected RIB ("show rib") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = 'a234:a234::1/128'
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
    # route a234:a234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route a234:a234::1/128 and its next-hops.
    route_ipv6_kernel_route1 = dict()
    route_ipv6_kernel_route1['Route'] = 'a234:a234::1' + '/' + '128'
    route_ipv6_kernel_route1['NumberNexthops'] = '4'
    route_ipv6_kernel_route1[sw1_intf1] = dict()
    route_ipv6_kernel_route1[sw1_intf1]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf2] = dict()
    route_ipv6_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf3] = dict()
    route_ipv6_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf4] = dict()
    route_ipv6_kernel_route1[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 2234:2234::1/128 and its next-hops.
    route_ipv6_kernel_route2 = dict()
    route_ipv6_kernel_route2['Route'] = '2234:2234::1' + '/' + '128'
    route_ipv6_kernel_route2['NumberNexthops'] = '1'
    route_ipv6_kernel_route2[sw1_intf4] = dict()
    route_ipv6_kernel_route2[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 3234:3234::1/128 and its next-hops.
    route_ipv6_kernel_route3 = dict()
    route_ipv6_kernel_route3['Route'] = '3234:3234::1' + '/' + '128'
    route_ipv6_kernel_route3['NumberNexthops'] = '1'
    route_ipv6_kernel_route3[sw1_intf2] = dict()
    route_ipv6_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4 static routes on switch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route1, 'zebra')

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route2, 'zebra')

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route3, 'zebra')

    step("Verifying the IPv6 static routes on switch 1")

    # Verify route a234:a234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route1, 'zebra')

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route2, 'zebra')

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route3, 'zebra')


# This test restarts zebra process and checks if the routes and next-hops show
# correctly in the output of "show ip route/show rib" after zebra has
# restarted. There is no configuration change when zebra is not running.
def restart_zebra_without_config_change(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step(
        "######### Restarting zebra without config changes on switch 1"
        "#########")

    step(
        "######### Restarting zebra. Stopping ops-zebra service on switch 1"
        "#########")

    # Execute the command to stop zebra on the Linux bash interface
    sw1(zebra_stop_command_string, shell='bash')

    step(
        "######### Restarting zebra. Starting ops-zebra service on switch 1"
        "#########")

    # Execute the command to start zebra on the Linux bash interface
    sw1(zebra_start_command_string, shell='bash')

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
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route 123.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route1 = dict()
    route_ipv4_kernel_route1['Route'] = '123.0.0.1' + '/' + '32'
    route_ipv4_kernel_route1['NumberNexthops'] = '4'
    route_ipv4_kernel_route1['1.1.1.2'] = dict()
    route_ipv4_kernel_route1['1.1.1.2']['Distance'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['Metric'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['RouteType'] = 'zebra'
    route_ipv4_kernel_route1[sw1_intf2] = dict()
    route_ipv4_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1[sw1_intf3] = dict()
    route_ipv4_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1['4.4.4.1'] = dict()
    route_ipv4_kernel_route1['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 143.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route2 = dict()
    route_ipv4_kernel_route2['Route'] = '143.0.0.1' + '/' + '32'
    route_ipv4_kernel_route2['NumberNexthops'] = '1'
    route_ipv4_kernel_route2['4.4.4.1'] = dict()
    route_ipv4_kernel_route2['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route3 = dict()
    route_ipv4_kernel_route3['Route'] = '163.0.0.1' + '/' + '32'
    route_ipv4_kernel_route3['NumberNexthops'] = '1'
    route_ipv4_kernel_route3[sw1_intf2] = dict()
    route_ipv4_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = 'a234:a234::1/128'
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
    # route a234:a234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route a234:a234::1/128 and its next-hops.
    route_ipv6_kernel_route1 = dict()
    route_ipv6_kernel_route1['Route'] = 'a234:a234::1' + '/' + '128'
    route_ipv6_kernel_route1['NumberNexthops'] = '4'
    route_ipv6_kernel_route1[sw1_intf1] = dict()
    route_ipv6_kernel_route1[sw1_intf1]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf2] = dict()
    route_ipv6_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf3] = dict()
    route_ipv6_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf4] = dict()
    route_ipv6_kernel_route1[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 2234:2234::1/128 and its next-hops.
    route_ipv6_kernel_route2 = dict()
    route_ipv6_kernel_route2['Route'] = '2234:2234::1' + '/' + '128'
    route_ipv6_kernel_route2['NumberNexthops'] = '1'
    route_ipv6_kernel_route2[sw1_intf4] = dict()
    route_ipv6_kernel_route2[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 3234:3234::1/128 and its next-hops.
    route_ipv6_kernel_route3 = dict()
    route_ipv6_kernel_route3['Route'] = '3234:3234::1' + '/' + '128'
    route_ipv6_kernel_route3['NumberNexthops'] = '1'
    route_ipv6_kernel_route3[sw1_intf2] = dict()
    route_ipv6_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4 static routes onswitch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    sw1("configure terminal")
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route1, 'zebra')

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route2, 'zebra')

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route3, 'zebra')

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route a234:a234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route1, 'zebra')

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route2, 'zebra')

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route3, 'zebra')


# This test restarts zebra process and checks if the routes and next-hops show
# correctly in the output of "show ip route/show rib" after zebra has
# restarted. While zebra is not running,, we change the static route
# configuration by deleting some routes and adding some new routes.
def restart_zebra_with_config_change(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("######### Restarting zebra with config changes on switch 1#########")

    step(
        "######### Restarting zebra. Stopping ops-zebra service on switch 1"
        "#########")

    # Execute the command to stop zebra on the Linux bash interface
    sw1(zebra_stop_command_string, shell='bash')

    step("######### Removing some static route configuration while zebra \
         is not running on switch 1#########")

    sw1('configure terminal')

    # Un-configure IPv4 route 123.0.0.1/32 with next-hop 1.1.1.2
    sw1('no ip route 123.0.0.1/32 1.1.1.2')

    # Un-configure IPv4 route 123.0.0.1/32 with next-hop 2
    sw1('no ip route 123.0.0.1/32 %s' % sw1_intf2)

    # Un-configure IPv4 route 143.0.0.1/32 next-hop 4.4.4.1.
    sw1('no ip route 143.0.0.1/32 4.4.4.1')

    # Un-configure IPv6 route a234:a234::1/128 with next-hop 1.
    sw1("no ipv6 route a234:a234::1/128 %s" % sw1_intf1)

    # Un-configure IPv6 route a234:a234::1/128 with next-hop 2.
    sw1("no ipv6 route a234:a234::1/128 %s" % sw1_intf2)

    # un-configure IPv6 route 3234:3234::1/128 with next-hop 2.
    sw1("no ipv6 route 3234:3234::1/128 %s" % sw1_intf2)

    # Configure IPv4 route 173.0.0.1/32 with next-hop 1.1.1.2
    sw1('ip route 173.0.0.1/32 1.1.1.2')

    # Configure IPv4 route 173.0.0.1/32 with next-hop 3
    sw1('ip route 173.0.0.1/32 %s' % sw1_intf3)

    # Configure IPv4 route 183.0.0.1/32 next-hop 4.4.4.1.
    sw1('ip route 183.0.0.1/32 4.4.4.1')

    # Configure IPv6 route 7234:7234::1/128 with next-hop 1.
    sw1('ipv6 route 7234:7234::1/128 %s' % sw1_intf1)

    # Configure IPv6 route 7234:7234::1/128 with next-hop 3.
    sw1('ipv6 route 7234:7234::1/128 %s' % sw1_intf3)

    # Configure IPv6 route 8234:8234::1/128 with next-hop 2.
    sw1('ipv6 route 8234:8234::1/128 %s' % sw1_intf2)

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'
    rib_ipv4_static_route1['NumberNexthops'] = '2'
    rib_ipv4_static_route1[sw1_intf3] = dict()
    rib_ipv4_static_route1[sw1_intf3]['Distance'] = '1'
    rib_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route 123.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route1 = dict()
    route_ipv4_kernel_route1['Route'] = '123.0.0.1/32'
    route_ipv4_kernel_route1['NumberNexthops'] = '2'
    route_ipv4_kernel_route1[sw1_intf3] = dict()
    route_ipv4_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1['4.4.4.1'] = dict()
    route_ipv4_kernel_route1['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['RouteType'] = 'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the version of the route in kernel in the route dictionary
    # for the route 143.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route2 = route_ipv4_static_route2

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route3 = dict()
    route_ipv4_kernel_route3['Route'] = '163.0.0.1' + '/' + '32'
    route_ipv4_kernel_route3['NumberNexthops'] = '1'
    route_ipv4_kernel_route3[sw1_intf2] = dict()
    route_ipv4_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 173.0.0.1/32 and its next-hops.
    rib_ipv4_static_route4 = dict()
    rib_ipv4_static_route4['Route'] = '173.0.0.1/32'
    rib_ipv4_static_route4['NumberNexthops'] = '2'
    rib_ipv4_static_route4[sw1_intf3] = dict()
    rib_ipv4_static_route4[sw1_intf3]['Distance'] = '1'
    rib_ipv4_static_route4[sw1_intf3]['Metric'] = '0'
    rib_ipv4_static_route4[sw1_intf3]['RouteType'] = \
        'static'
    rib_ipv4_static_route4['1.1.1.2'] = dict()
    rib_ipv4_static_route4['1.1.1.2']['Distance'] = '1'
    rib_ipv4_static_route4['1.1.1.2']['Metric'] = '0'
    rib_ipv4_static_route4['1.1.1.2']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 173.0.0.1/32 and its next-hops.
    route_ipv4_static_route4 = rib_ipv4_static_route4

    # Populate the version of the route in kernel in the route dictionary
    # for the route 173.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route4 = dict()
    route_ipv4_kernel_route4['Route'] = '173.0.0.1' + '/' + '32'
    route_ipv4_kernel_route4['NumberNexthops'] = '2'
    route_ipv4_kernel_route4[sw1_intf3] = dict()
    route_ipv4_kernel_route4[sw1_intf3]['Distance'] = ''
    route_ipv4_kernel_route4[sw1_intf3]['Metric'] = ''
    route_ipv4_kernel_route4[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route4['1.1.1.2'] = dict()
    route_ipv4_kernel_route4['1.1.1.2']['Distance'] = ''
    route_ipv4_kernel_route4['1.1.1.2']['Metric'] = ''
    route_ipv4_kernel_route4['1.1.1.2']['RouteType'] = 'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 183.0.0.1/32 and its next-hops.
    rib_ipv4_static_route5 = dict()
    rib_ipv4_static_route5['Route'] = '183.0.0.1/32'
    rib_ipv4_static_route5['NumberNexthops'] = '1'
    rib_ipv4_static_route5['4.4.4.1'] = dict()
    rib_ipv4_static_route5['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route5['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route5['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 183.0.0.1/32 and its next-hops.
    route_ipv4_static_route5 = rib_ipv4_static_route5

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route5 = dict()
    route_ipv4_kernel_route5['Route'] = '183.0.0.1/32'
    route_ipv4_kernel_route5['NumberNexthops'] = '1'
    route_ipv4_kernel_route5['4.4.4.1'] = dict()
    route_ipv4_kernel_route5['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route5['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route5['4.4.4.1']['RouteType'] = 'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = 'a234:a234::1/128'
    rib_ipv6_static_route1['NumberNexthops'] = '2'
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
    # route a234:a234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route a234:a234::1/128 and its next-hops.
    route_ipv6_kernel_route1 = dict()
    route_ipv6_kernel_route1['Route'] = 'a234:a234::1' + '/' + '128'
    route_ipv6_kernel_route1['NumberNexthops'] = '2'
    route_ipv6_kernel_route1[sw1_intf3] = dict()
    route_ipv6_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf4] = dict()
    route_ipv6_kernel_route1[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 2234:2234::1/128 and its next-hops.
    route_ipv6_kernel_route2 = dict()
    route_ipv6_kernel_route2['Route'] = '2234:2234::1' + '/' + '128'
    route_ipv6_kernel_route2['NumberNexthops'] = '1'
    route_ipv6_kernel_route2[sw1_intf4] = dict()
    route_ipv6_kernel_route2[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['RouteType'] = \
        'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    # Populate the version of the route in kernel in the route dictionary
    # for the route 3234:3234::1/128 and its next-hops.
    route_ipv6_kernel_route3 = route_ipv6_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 7234:7234::1/128 and its next-hops.
    rib_ipv6_static_route4 = dict()
    rib_ipv6_static_route4['Route'] = '7234:7234::1/128'
    rib_ipv6_static_route4['NumberNexthops'] = '2'
    rib_ipv6_static_route4[sw1_intf1] = dict()
    rib_ipv6_static_route4[sw1_intf1]['Distance'] = '1'
    rib_ipv6_static_route4[sw1_intf1]['Metric'] = '0'
    rib_ipv6_static_route4[sw1_intf1]['RouteType'] = \
        'static'
    rib_ipv6_static_route4[sw1_intf3] = dict()
    rib_ipv6_static_route4[sw1_intf3]['Distance'] = '1'
    rib_ipv6_static_route4[sw1_intf3]['Metric'] = '0'
    rib_ipv6_static_route4[sw1_intf3]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 7234:7234::1/128 and its next-hops.
    route_ipv6_static_route4 = rib_ipv6_static_route4

    # Populate the version of the route in kernel in the route dictionary
    # for the route 7234:7234::1/128 and its next-hops.
    route_ipv6_kernel_route4 = dict()
    route_ipv6_kernel_route4['Route'] = '7234:7234::1' + '/' + '128'
    route_ipv6_kernel_route4['NumberNexthops'] = '2'
    route_ipv6_kernel_route4[sw1_intf1] = dict()
    route_ipv6_kernel_route4[sw1_intf1]['Distance'] = ''
    route_ipv6_kernel_route4[sw1_intf1]['Metric'] = ''
    route_ipv6_kernel_route4[sw1_intf1]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route4[sw1_intf3] = dict()
    route_ipv6_kernel_route4[sw1_intf3]['Distance'] = ''
    route_ipv6_kernel_route4[sw1_intf3]['Metric'] = ''
    route_ipv6_kernel_route4[sw1_intf3]['RouteType'] = \
        'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 8234:8234::1/128 and its next-hops.
    rib_ipv6_static_route5 = dict()
    rib_ipv6_static_route5['Route'] = '8234:8234::1/128'
    rib_ipv6_static_route5['NumberNexthops'] = '1'
    rib_ipv6_static_route5[sw1_intf2] = dict()
    rib_ipv6_static_route5[sw1_intf2]['Distance'] = '1'
    rib_ipv6_static_route5[sw1_intf2]['Metric'] = '0'
    rib_ipv6_static_route5[sw1_intf2]['RouteType'] = \
        'static'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 8234:8234::1/128 and its next-hops.
    route_ipv6_static_route5 = rib_ipv6_static_route5

    # Populate the version of the route in kernel in the route dictionary
    # for the route 8234:8234::1/128 and its next-hops.
    route_ipv6_kernel_route5 = dict()
    route_ipv6_kernel_route5['Route'] = '8234:8234::1' + '/' + '128'
    route_ipv6_kernel_route5['NumberNexthops'] = '1'
    route_ipv6_kernel_route5[sw1_intf2] = dict()
    route_ipv6_kernel_route5[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route5[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route5[sw1_intf2]['RouteType'] = \
        'zebra'

    step(
        "######### Restarting zebra. Starting ops-zebra service on switch 1"
        "#########")

    # Execute the command to start zebra on the Linux bash interface
    sw1(zebra_start_command_string, shell='bash')

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4 static routes on switch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    sw1("configure terminal")
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route1, 'zebra')

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route2, 'zebra')

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route3, 'zebra')

    # Verify route 173.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route4["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route4)
    aux_route = rib_ipv4_static_route4["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route4)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route4, 'zebra')

    # Verify route 183.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route5["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route5)
    aux_route = rib_ipv4_static_route5["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route5)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route5, 'zebra')

    step("Verifying the IPv6 static routes on switch 1")

    # Verify route a234:a234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route1, 'zebra')

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route2, 'zebra')

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route3, 'zebra')

    # Verify route 7234:7234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route4["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route4)
    aux_route = rib_ipv6_static_route4["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route4)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route4, 'zebra')

    # Verify route 8234:8234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route5["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route5)
    aux_route = rib_ipv6_static_route5["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route5)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route5, 'zebra')


# This test restarts zebra process and checks if the routes and next-hops show
# correctly in the output of "show ip route/show rib" after zebra has
# restarted. After zebra has come back up from restart, we change the static
# route configuration by deleting some routes and adding some new routes.
def config_change_after_zebra_restart(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("\n\n\n######### Restarting zebra. Stopping ops-zebra service on"
         "switch 1#########")

    # Execute the command to stop zebra on the Linux bash interface
    sw1(zebra_stop_command_string, shell='bash')

    step("\n\n\n######### Restarting zebra. Starting ops-zebra service on"
         "switch 1#########")

    # Execute the command to start zebra on the Linux bash interface
    sw1(zebra_start_command_string, shell='bash')

    step("\n\n\n######### Adding some static route configuration "
         " after zebra has restarted on switch 1#########")

    sw1('configure terminal')
    # Configure IPv4 route 123.0.0.1/32 with next-hop 1.1.1.2
    sw1('ip route 123.0.0.1/32 1.1.1.2')

    # Configure IPv4 route 123.0.0.1/32 with next-hop 2
    sw1('ip route 123.0.0.1/32 %s' % sw1_intf2)

    # Configure IPv4 route 143.0.0.1/32 next-hop 4.4.4.1.
    sw1('ip route 143.0.0.1/32 4.4.4.1')

    # Configure IPv6 route a234:a234::1/128 with next-hop 1.
    sw1("ipv6 route a234:a234::1/128 %s" % sw1_intf1)

    # Configure IPv6 route a234:a234::1/128 with next-hop 2.
    sw1("ipv6 route a234:a234::1/128 %s" % sw1_intf2)

    # Configure IPv6 route 3234:3234::1/128 with next-hop 2.
    sw1("ipv6 route 3234:3234::1/128 %s" % sw1_intf2)

    # Un-configure IPv4 route 173.0.0.1/32 with next-hop 1.1.1.2
    sw1('no ip route 173.0.0.1/32 1.1.1.2')

    # Un-configure IPv4 route 173.0.0.1/32 with next-hop 3
    sw1('no ip route 173.0.0.1/32 %s' % sw1_intf3)

    # Un-configure IPv4 route 183.0.0.1/32 next-hop 4.4.4.1.
    sw1('no ip route 183.0.0.1/32 4.4.4.1')

    # Un-configure IPv6 route 7234:7234::1/128 with next-hop 1.
    sw1('no ipv6 route 7234:7234::1/128 %s' % sw1_intf1)

    # Un-configure IPv6 route 7234:7234::1/128 with next-hop 3.
    sw1('no ipv6 route 7234:7234::1/128 %s' % sw1_intf3)

    # Un-configure IPv6 route 8234:8234::1/128 with next-hop 2.
    sw1('no ipv6 route 8234:8234::1/128 %s' % sw1_intf2)

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
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route 123.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route1 = dict()
    route_ipv4_kernel_route1['Route'] = '123.0.0.1' + '/' + '32'
    route_ipv4_kernel_route1['NumberNexthops'] = '4'
    route_ipv4_kernel_route1['1.1.1.2'] = dict()
    route_ipv4_kernel_route1['1.1.1.2']['Distance'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['Metric'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['RouteType'] = 'zebra'
    route_ipv4_kernel_route1[sw1_intf2] = dict()
    route_ipv4_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1[sw1_intf3] = dict()
    route_ipv4_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1['4.4.4.1'] = dict()
    route_ipv4_kernel_route1['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 143.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route2 = dict()
    route_ipv4_kernel_route2['Route'] = '143.0.0.1' + '/' + '32'
    route_ipv4_kernel_route2['NumberNexthops'] = '1'
    route_ipv4_kernel_route2['4.4.4.1'] = dict()
    route_ipv4_kernel_route2['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route3 = dict()
    route_ipv4_kernel_route3['Route'] = '163.0.0.1' + '/' + '32'
    route_ipv4_kernel_route3['NumberNexthops'] = '1'
    route_ipv4_kernel_route3[sw1_intf2] = dict()
    route_ipv4_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 173.0.0.1/32 and its next-hops.
    rib_ipv4_static_route4 = dict()
    rib_ipv4_static_route4['Route'] = '173.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 173.0.0.1/32 and its next-hops.
    route_ipv4_static_route4 = rib_ipv4_static_route4

    # Populate the version of the route in kernel in the route dictionary
    # for the route 173.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route4 = route_ipv4_static_route4

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 183.0.0.1/32 and its next-hops.
    rib_ipv4_static_route5 = dict()
    rib_ipv4_static_route5['Route'] = '183.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 183.0.0.1/32 and its next-hops.
    route_ipv4_static_route5 = rib_ipv4_static_route5

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route5 = route_ipv4_static_route5

    # Populate the expected RIB ("show rib") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = 'a234:a234::1/128'
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
    # route a234:a234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route a234:a234::1/128 and its next-hops.
    route_ipv6_kernel_route1 = dict()
    route_ipv6_kernel_route1['Route'] = 'a234:a234::1' + '/' + '128'
    route_ipv6_kernel_route1['NumberNexthops'] = '4'
    route_ipv6_kernel_route1[sw1_intf1] = dict()
    route_ipv6_kernel_route1[sw1_intf1]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf2] = dict()
    route_ipv6_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf3] = dict()
    route_ipv6_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf4] = dict()
    route_ipv6_kernel_route1[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 2234:2234::1/128 and its next-hops.
    route_ipv6_kernel_route2 = dict()
    route_ipv6_kernel_route2['Route'] = '2234:2234::1' + '/' + '128'
    route_ipv6_kernel_route2['NumberNexthops'] = '1'
    route_ipv6_kernel_route2[sw1_intf4] = dict()
    route_ipv6_kernel_route2[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 3234:3234::1/128 and its next-hops.
    route_ipv6_kernel_route3 = dict()
    route_ipv6_kernel_route3['Route'] = '3234:3234::1' + '/' + '128'
    route_ipv6_kernel_route3['NumberNexthops'] = '1'
    route_ipv6_kernel_route3[sw1_intf2] = dict()
    route_ipv6_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 7234:7234::1/128 and its next-hops.
    rib_ipv6_static_route4 = dict()
    rib_ipv6_static_route4['Route'] = '7234:7234::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 7234:7234::1/128 and its next-hops.
    route_ipv6_static_route4 = rib_ipv6_static_route4

    # Populate the version of the route in kernel in the route dictionary
    # for the route 7234:7234::1/128 and its next-hops.
    route_ipv6_kernel_route4 = route_ipv6_static_route4

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 8234:8234::1/128 and its next-hops.
    rib_ipv6_static_route5 = dict()
    rib_ipv6_static_route5['Route'] = '8234:8234::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 8234:8234::1/128 and its next-hops.
    route_ipv6_static_route5 = rib_ipv6_static_route5

    # Populate the version of the route in kernel in the route dictionary
    # for the route 8234:8234::1/128 and its next-hops.
    route_ipv6_kernel_route5 = route_ipv6_static_route5

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4 static routes onswitch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route1, 'zebra')

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route2, 'zebra')

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route3, 'zebra')

    # Verify route 173.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route4["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route4)
    aux_route = rib_ipv4_static_route4["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route4)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route4, 'zebra')

    # Verify route 183.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route5["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route5)
    aux_route = rib_ipv4_static_route5["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route5)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route5, 'zebra')

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route a234:a234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route1, 'zebra')

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route2, 'zebra')

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route3, 'zebra')

    # Verify route 7234:7234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route4["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route4)
    aux_route = rib_ipv6_static_route4["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route4)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route4, 'zebra')

    # Verify route 8234:8234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route5["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route5)
    aux_route = rib_ipv6_static_route5["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route5)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route5, 'zebra')


# This test restarts zebra process and checks if the routes and next-hops show
# correctly in the output of "show ip route/show rib" after zebra has
# restarted. Before zebra has come back up from restart, we shutdown some
# next-hop interfaces.
def interface_down_before_zebra_restart(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("\n\n\n######### Restarting zebra and shutting down"
         " some next-hop interfaces on switch1.#########")

    step("\n\n\n######### Restarting zebra. Stopping ops-zebra service on"
         "switch 1#########")

    # Execute the command to stop zebra on the Linux bash interface
    sw1(zebra_stop_command_string, shell='bash')

    # Shut down interface 2 on switch1
    sw1('configure terminal')
    sw1("interface %s" % sw1_intf2)
    sw1('shutdown')

    step("\n\n\n######### Restarting zebra. Starting ops-zebra service on"
         "switch 1#########")

    # Execute the command to start zebra on the Linux bash interface
    sw1(zebra_start_command_string, shell='bash')

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
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = dict()
    route_ipv4_static_route1['Route'] = '123.0.0.1/32'
    route_ipv4_static_route1['NumberNexthops'] = '3'
    route_ipv4_static_route1['1.1.1.2'] = dict()
    route_ipv4_static_route1['1.1.1.2']['Distance'] = '1'
    route_ipv4_static_route1['1.1.1.2']['Metric'] = '0'
    route_ipv4_static_route1['1.1.1.2']['RouteType'] = 'static'
    route_ipv4_static_route1[sw1_intf3] = dict()
    route_ipv4_static_route1[sw1_intf3]['Distance'] = '1'
    route_ipv4_static_route1[sw1_intf3]['Metric'] = '0'
    route_ipv4_static_route1[sw1_intf3]['RouteType'] = \
        'static'
    route_ipv4_static_route1['4.4.4.1'] = dict()
    route_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    route_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    route_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the version of the route in kernel in the route dictionary
    # for the route 123.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route1 = dict()
    route_ipv4_kernel_route1['Route'] = '123.0.0.1' + '/' + '32'
    route_ipv4_kernel_route1['NumberNexthops'] = '3'
    route_ipv4_kernel_route1['1.1.1.2'] = dict()
    route_ipv4_kernel_route1['1.1.1.2']['Distance'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['Metric'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['RouteType'] = 'zebra'
    route_ipv4_kernel_route1[sw1_intf3] = dict()
    route_ipv4_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1['4.4.4.1'] = dict()
    route_ipv4_kernel_route1['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 143.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route2 = dict()
    route_ipv4_kernel_route2['Route'] = '143.0.0.1' + '/' + '32'
    route_ipv4_kernel_route2['NumberNexthops'] = '1'
    route_ipv4_kernel_route2['4.4.4.1'] = dict()
    route_ipv4_kernel_route2['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['RouteType'] = 'zebra'

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
    route_ipv4_static_route3 = dict()
    route_ipv4_static_route3['Route'] = '163.0.0.1/32'

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route3 = dict()
    route_ipv4_kernel_route3['Route'] = '163.0.0.1' + '/' + '32'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = 'a234:a234::1/128'
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
    # route a234:a234::1/128 and its next-hops.
    route_ipv6_static_route1 = dict()
    route_ipv6_static_route1['Route'] = 'a234:a234::1/128'
    route_ipv6_static_route1['NumberNexthops'] = '3'
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
    route_ipv6_static_route1[sw1_intf4] = dict()
    route_ipv6_static_route1[sw1_intf4]['Distance'] = '1'
    route_ipv6_static_route1[sw1_intf4]['Metric'] = '0'
    route_ipv6_static_route1[sw1_intf4]['RouteType'] = \
        'static'

    # Populate the version of the route in kernel in the route dictionary
    # for the route a234:a234::1/128 and its next-hops.
    route_ipv6_kernel_route1 = dict()
    route_ipv6_kernel_route1['Route'] = 'a234:a234::1' + '/' + '128'
    route_ipv6_kernel_route1['NumberNexthops'] = '3'
    route_ipv6_kernel_route1[sw1_intf1] = dict()
    route_ipv6_kernel_route1[sw1_intf1]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf3] = dict()
    route_ipv6_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf4] = dict()
    route_ipv6_kernel_route1[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 2234:2234::1/128 and its next-hops.
    route_ipv6_kernel_route2 = dict()
    route_ipv6_kernel_route2['Route'] = '2234:2234::1' + '/' + '128'
    route_ipv6_kernel_route2['NumberNexthops'] = '1'
    route_ipv6_kernel_route2[sw1_intf4] = dict()
    route_ipv6_kernel_route2[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['RouteType'] = \
        'zebra'

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
    route_ipv6_static_route3 = dict()
    route_ipv6_static_route3['Route'] = '3234:3234::1/128'

    # Populate the version of the route in kernel in the route dictionary
    # for the route 3234:3234::1/128 and its next-hops.
    route_ipv6_kernel_route3 = dict()
    route_ipv6_kernel_route3['Route'] = '3234:3234::1' + '/' + '128'

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4 static routes onswitch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    sw1('configure terminal')
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route1, 'zebra')

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route2, 'zebra')

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route3, 'zebra')

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route a234:a234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route1, 'zebra')

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route2, 'zebra')

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route3, 'zebra')


# This test restarts zebra process and checks if the routes and next-hops show
# correctly in the output of "show ip route/show rib" after zebra has
# restarted. Before zebra has come back up from restart, we un-shutdown some
# next-hop interfaces.
def interface_up_before_zebra_restart(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("\n\n\n######### Restarting zebra and un-shutting"
         " some next-hop interfaces on switch1.#########")

    step("\n\n\n######### Restarting zebra. Stopping ops-zebra service on"
         "switch 1#########")

    # Execute the command to stop zebra on the Linux bash interface
    sw1(zebra_stop_command_string, shell='bash')

    # Shut down interface 2 on switch1
    sw1('configure terminal')
    sw1("interface %s" % sw1_intf2)
    sw1('no shutdown')

    step("\n\n\n######### Restarting zebra. Starting ops-zebra service on"
         "switch 1#########")

    # Execute the command to start zebra on the Linux bash interface
    sw1(zebra_start_command_string, shell='bash')

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
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route 123.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route1 = dict()
    route_ipv4_kernel_route1['Route'] = '123.0.0.1' + '/' + '32'
    route_ipv4_kernel_route1['NumberNexthops'] = '4'
    route_ipv4_kernel_route1['1.1.1.2'] = dict()
    route_ipv4_kernel_route1['1.1.1.2']['Distance'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['Metric'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['RouteType'] = 'zebra'
    route_ipv4_kernel_route1[sw1_intf2] = dict()
    route_ipv4_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1[sw1_intf3] = dict()
    route_ipv4_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1['4.4.4.1'] = dict()
    route_ipv4_kernel_route1['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 143.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route2 = dict()
    route_ipv4_kernel_route2['Route'] = '143.0.0.1' + '/' + '32'
    route_ipv4_kernel_route2['NumberNexthops'] = '1'
    route_ipv4_kernel_route2['4.4.4.1'] = dict()
    route_ipv4_kernel_route2['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route3 = dict()
    route_ipv4_kernel_route3['Route'] = '163.0.0.1' + '/' + '32'
    route_ipv4_kernel_route3['NumberNexthops'] = '1'
    route_ipv4_kernel_route3[sw1_intf2] = dict()
    route_ipv4_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = 'a234:a234::1/128'
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
    # route a234:a234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route a234:a234::1/128 and its next-hops.
    route_ipv6_kernel_route1 = dict()
    route_ipv6_kernel_route1['Route'] = 'a234:a234::1' + '/' + '128'
    route_ipv6_kernel_route1['NumberNexthops'] = '4'
    route_ipv6_kernel_route1[sw1_intf1] = dict()
    route_ipv6_kernel_route1[sw1_intf1]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf2] = dict()
    route_ipv6_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf3] = dict()
    route_ipv6_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf4] = dict()
    route_ipv6_kernel_route1[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 2234:2234::1/128 and its next-hops.
    route_ipv6_kernel_route2 = dict()
    route_ipv6_kernel_route2['Route'] = '2234:2234::1' + '/' + '128'
    route_ipv6_kernel_route2['NumberNexthops'] = '1'
    route_ipv6_kernel_route2[sw1_intf4] = dict()
    route_ipv6_kernel_route2[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 3234:3234::1/128 and its next-hops.
    route_ipv6_kernel_route3 = dict()
    route_ipv6_kernel_route3['Route'] = '3234:3234::1' + '/' + '128'
    route_ipv6_kernel_route3['NumberNexthops'] = '1'
    route_ipv6_kernel_route3[sw1_intf2] = dict()
    route_ipv6_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4 static routes onswitch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    sw1('configure terminal')
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route1, 'zebra')

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route2, 'zebra')

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route3, 'zebra')

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route a234:a234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route1, 'zebra')

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route2, 'zebra')

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route3, 'zebra')


# This test restarts zebra process and checks if the routes and next-hops show
# correctly in the output of "show ip route/show rib" after zebra has
# restarted. Before zebra has come back up from restart, we change interface
# addresses on some interfaces.
def interface_addr_change_before_zebra_restart(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("\n\n\n######### Restarting zebra and changing "
         " some interface addresses on switch1.#########")

    step("\n\n\n######### Restarting zebra. Stopping ops-zebra service on"
         "switch 1#########")

    # Execute the command to stop zebra on the Linux bash interface
    sw1(zebra_stop_command_string, shell='bash')

    # Re-configure IPv4 and IPv6 address on interface 1 on switch1
    sw1('configure terminal')
    sw1("interface %s" % sw1_intf1)
    sw1('ip address 9.9.9.9/24')
    sw1('ipv6 address 999:999::9/64')

    step("\n\n\n######### Restarting zebra. Starting ops-zebra service on"
         "switch 1#########")

    # Execute the command to start zebra on the Linux bash interface
    sw1(zebra_start_command_string, shell='bash')

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
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
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
    route_ipv4_static_route1['4.4.4.1'] = dict()
    route_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    route_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    route_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the version of the route in kernel in the route dictionary
    # for the route 123.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route1 = dict()
    route_ipv4_kernel_route1['Route'] = '123.0.0.1' + '/' + '32'
    route_ipv4_kernel_route1['NumberNexthops'] = '3'
    route_ipv4_kernel_route1[sw1_intf2] = dict()
    route_ipv4_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1[sw1_intf3] = dict()
    route_ipv4_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1['4.4.4.1'] = dict()
    route_ipv4_kernel_route1['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 143.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route2 = dict()
    route_ipv4_kernel_route2['Route'] = '143.0.0.1' + '/' + '32'
    route_ipv4_kernel_route2['NumberNexthops'] = '1'
    route_ipv4_kernel_route2['4.4.4.1'] = dict()
    route_ipv4_kernel_route2['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route3 = dict()
    route_ipv4_kernel_route3['Route'] = '163.0.0.1' + '/' + '32'
    route_ipv4_kernel_route3['NumberNexthops'] = '1'
    route_ipv4_kernel_route3[sw1_intf2] = dict()
    route_ipv4_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = 'a234:a234::1/128'
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
    # route a234:a234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route a234:a234::1/128 and its next-hops.
    route_ipv6_kernel_route1 = dict()
    route_ipv6_kernel_route1['Route'] = 'a234:a234::1' + '/' + '128'
    route_ipv6_kernel_route1['NumberNexthops'] = '4'
    route_ipv6_kernel_route1[sw1_intf1] = dict()
    route_ipv6_kernel_route1[sw1_intf1]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf2] = dict()
    route_ipv6_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf3] = dict()
    route_ipv6_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf4] = dict()
    route_ipv6_kernel_route1[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 2234:2234::1/128 and its next-hops.
    route_ipv6_kernel_route2 = dict()
    route_ipv6_kernel_route2['Route'] = '2234:2234::1' + '/' + '128'
    route_ipv6_kernel_route2['NumberNexthops'] = '1'
    route_ipv6_kernel_route2[sw1_intf4] = dict()
    route_ipv6_kernel_route2[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 3234:3234::1/128 and its next-hops.
    route_ipv6_kernel_route3 = dict()
    route_ipv6_kernel_route3['Route'] = '3234:3234::1' + '/' + '128'
    route_ipv6_kernel_route3['NumberNexthops'] = '1'
    route_ipv6_kernel_route3[sw1_intf2] = dict()
    route_ipv6_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4 static routes onswitch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    sw1('configure terminal')
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route1, 'zebra')

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route2, 'zebra')

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route3, 'zebra')

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route a234:a234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route1, 'zebra')

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route2, 'zebra')

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route3, 'zebra')


# This test restarts zebra process and checks if the routes and next-hops show
# correctly in the output of "show ip route/show rib" after zebra has
# restarted. Before zebra has come back up from restart, we restore interface
# addresses on the interfaces on which we changed the addresses on in the test
# case interface_addr_change_before_zebra_restart.
def interface_addr_restore_before_zebra_restart(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("\n\n\n######### Restarting zebra and restoring "
         " some interface addresses on switch1.#########")

    step("\n\n\n######### Restarting zebra. Stopping ops-zebra service on"
         "switch 1#########")

    # Execute the command to stop zebra on the Linux bash interface
    sw1(zebra_stop_command_string, shell='bash')

    # Re-configure IPv4 and IPv6 address on interface 1 on switch1
    sw1('configure terminal')
    sw1("interface %s" % sw1_intf1)
    sw1('ip address 1.1.1.1/24')
    sw1('ipv6 address 111:111::1/64')

    step("\n\n\n######### Restarting zebra. Starting ops-zebra service on"
         "switch 1#########")

    # Execute the command to start zebra on the Linux bash interface
    sw1(zebra_start_command_string, shell='bash')

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
    rib_ipv4_static_route1['4.4.4.1'] = dict()
    rib_ipv4_static_route1['4.4.4.1']['Distance'] = '1'
    rib_ipv4_static_route1['4.4.4.1']['Metric'] = '0'
    rib_ipv4_static_route1['4.4.4.1']['RouteType'] = 'static'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route 123.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route1 = dict()
    route_ipv4_kernel_route1['Route'] = '123.0.0.1' + '/' + '32'
    route_ipv4_kernel_route1['NumberNexthops'] = '4'
    route_ipv4_kernel_route1['1.1.1.2'] = dict()
    route_ipv4_kernel_route1['1.1.1.2']['Distance'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['Metric'] = ''
    route_ipv4_kernel_route1['1.1.1.2']['RouteType'] = 'zebra'
    route_ipv4_kernel_route1[sw1_intf2] = dict()
    route_ipv4_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1[sw1_intf3] = dict()
    route_ipv4_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv4_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv4_kernel_route1['4.4.4.1'] = dict()
    route_ipv4_kernel_route1['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route1['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 143.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route2 = dict()
    route_ipv4_kernel_route2['Route'] = '143.0.0.1' + '/' + '32'
    route_ipv4_kernel_route2['NumberNexthops'] = '1'
    route_ipv4_kernel_route2['4.4.4.1'] = dict()
    route_ipv4_kernel_route2['4.4.4.1']['Distance'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['Metric'] = ''
    route_ipv4_kernel_route2['4.4.4.1']['RouteType'] = 'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route3 = dict()
    route_ipv4_kernel_route3['Route'] = '163.0.0.1' + '/' + '32'
    route_ipv4_kernel_route3['NumberNexthops'] = '1'
    route_ipv4_kernel_route3[sw1_intf2] = dict()
    route_ipv4_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv4_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    # Populate the expected RIB ("show rib") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = 'a234:a234::1/128'
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
    # route a234:a234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route a234:a234::1/128 and its next-hops.
    route_ipv6_kernel_route1 = dict()
    route_ipv6_kernel_route1['Route'] = 'a234:a234::1' + '/' + '128'
    route_ipv6_kernel_route1['NumberNexthops'] = '4'
    route_ipv6_kernel_route1[sw1_intf1] = dict()
    route_ipv6_kernel_route1[sw1_intf1]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf1]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf2] = dict()
    route_ipv6_kernel_route1[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf2]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf3] = dict()
    route_ipv6_kernel_route1[sw1_intf3]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf3]['RouteType'] = \
        'zebra'
    route_ipv6_kernel_route1[sw1_intf4] = dict()
    route_ipv6_kernel_route1[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route1[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 2234:2234::1/128 and its next-hops.
    route_ipv6_kernel_route2 = dict()
    route_ipv6_kernel_route2['Route'] = '2234:2234::1' + '/' + '128'
    route_ipv6_kernel_route2['NumberNexthops'] = '1'
    route_ipv6_kernel_route2[sw1_intf4] = dict()
    route_ipv6_kernel_route2[sw1_intf4]['Distance'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['Metric'] = ''
    route_ipv6_kernel_route2[sw1_intf4]['RouteType'] = \
        'zebra'

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

    # Populate the version of the route in kernel in the route dictionary
    # for the route 3234:3234::1/128 and its next-hops.
    route_ipv6_kernel_route3 = dict()
    route_ipv6_kernel_route3['Route'] = '3234:3234::1' + '/' + '128'
    route_ipv6_kernel_route3['NumberNexthops'] = '1'
    route_ipv6_kernel_route3[sw1_intf2] = dict()
    route_ipv6_kernel_route3[sw1_intf2]['Distance'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['Metric'] = ''
    route_ipv6_kernel_route3[sw1_intf2]['RouteType'] = \
        'zebra'

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4 static routes on switch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    sw1('configure terminal')
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route1, 'zebra')

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route2, 'zebra')

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route3, 'zebra')

    step("Verifying the IPv6 static routes onswitch 1")

    # Verify route a234:a234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route1, 'zebra')

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route2, 'zebra')

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route3, 'zebra')


# This test case deletes all static route configuration after zebra process
# is torn down. When zebra process comes up from restart it should clean-up
# the Kernel from the deleted static routes.
def all_configuration_deleted_before_zebra_restart(sw1, sw2, step):

    sw1_intf1 = format(sw1.ports["if01"])
    sw1_intf2 = format(sw1.ports["if02"])
    sw1_intf3 = format(sw1.ports["if03"])
    sw1_intf4 = format(sw1.ports["if04"])

    step("\n\n\n######### Restarting zebra and deleting all"
         " route configuration on switch1.#########")

    step("\n\n\n######### Restarting zebra. Stopping ops-zebra service on"
         "switch 1#########")

    # Execute the command to stop zebra on the Linux bash interface
    sw1(zebra_stop_command_string, shell='bash')

    # Un-configure IPv4 route 123.0.0.1/32 and all its next-hops
    sw1('configure terminal')
    sw1('no ip route 123.0.0.1/32 1.1.1.2')
    sw1('no ip route 123.0.0.1/32 %s' % sw1_intf2)
    sw1('no ip route 123.0.0.1/32 %s' % sw1_intf3)
    sw1('no ip route 123.0.0.1/32 4.4.4.1')

    # Un-configure IPv4 route 143.0.0.1/32 next-hop 4.4.4.1.
    sw1('no ip route 143.0.0.1/32 4.4.4.1')

    # Un-configure IPv4 route 163.0.0.1/32 next-hop 2.
    sw1('no ip route 163.0.0.1/32 %s' % sw1_intf2)

    # Un-configure IPv6 route a234:a234::1/128 and all its next-hops
    sw1("no ipv6 route a234:a234::1/128 %s" % sw1_intf1)
    sw1("no ipv6 route a234:a234::1/128 %s" % sw1_intf2)
    sw1("no ipv6 route a234:a234::1/128 %s" % sw1_intf3)
    sw1("no ipv6 route a234:a234::1/128 %s" % sw1_intf4)

    # Un-configure IPv6 route 2234:2234::1/128 with next-hop 1.
    sw1('no ipv6 route 2234:2234::1/128 %s' % sw1_intf4)

    # un-configure IPv6 route 3234:3234::1/128 with next-hop 2.
    sw1("no ipv6 route 3234:3234::1/128 %s" % sw1_intf2)

    step("\n\n\n######### Restarting zebra. Starting ops-zebra service on"
         "switch 1#########")

    # Execute the command to start zebra on the Linux bash interface
    sw1(zebra_start_command_string, shell='bash')

    # Populate the expected RIB ("show rib") route dictionary for the route
    # 123.0.0.1/32 and its next-hops.
    rib_ipv4_static_route1 = dict()
    rib_ipv4_static_route1['Route'] = '123.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 123.0.0.1/32 and its next-hops.
    route_ipv4_static_route1 = rib_ipv4_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route 123.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route1 = route_ipv4_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    rib_ipv4_static_route2 = dict()
    rib_ipv4_static_route2['Route'] = '143.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 143.0.0.1/32 and its next-hops.
    route_ipv4_static_route2 = rib_ipv4_static_route2

    # Populate the version of the route in kernel in the route dictionary
    # for the route 143.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route2 = route_ipv4_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 163.0.0.1/32 and its next-hops.
    rib_ipv4_static_route3 = dict()
    rib_ipv4_static_route3['Route'] = '163.0.0.1/32'

    # Populate the expected FIB ("show ip route") route dictionary for the
    # route 163.0.0.1/32 and its next-hops.
    route_ipv4_static_route3 = rib_ipv4_static_route3

    # Populate the version of the route in kernel in the route dictionary
    # for the route 163.0.0.1/32 and its next-hops.
    route_ipv4_kernel_route3 = route_ipv4_static_route3

    # Populate the expected RIB ("show rib") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    rib_ipv6_static_route1 = dict()
    rib_ipv6_static_route1['Route'] = 'a234:a234::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route a234:a234::1/128 and its next-hops.
    route_ipv6_static_route1 = rib_ipv6_static_route1

    # Populate the version of the route in kernel in the route dictionary
    # for the route a234:a234::1/128 and its next-hops.
    route_ipv6_kernel_route1 = route_ipv6_static_route1

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 2234:2234::1/128 and its next-hops.
    rib_ipv6_static_route2 = dict()
    rib_ipv6_static_route2['Route'] = '2234:2234::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 2234:2234::1/128 and its next-hops.
    route_ipv6_static_route2 = rib_ipv6_static_route2

    # Populate the version of the route in kernel in the route dictionary
    # for the route 2234:2234::1/128 and its next-hops.
    route_ipv6_kernel_route2 = route_ipv6_static_route2

    # Populate the expected RIB ("show rib") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    rib_ipv6_static_route3 = dict()
    rib_ipv6_static_route3['Route'] = '3234:3234::1/128'

    # Populate the expected FIB ("show ipv6 route") route dictionary for the
    # route 3234:3234::1/128 and its next-hops.
    route_ipv6_static_route3 = rib_ipv6_static_route3

    # Populate the version of the route in kernel in the route dictionary
    # for the route 3234:3234::1/128 and its next-hops.
    route_ipv6_kernel_route3 = route_ipv6_static_route3

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4 static routes on switch 1")

    # Verify route 123.0.0.1/32 and next-hops in RIB and FIB
    sw1('configure terminal')
    aux_route = route_ipv4_static_route1["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route1)
    aux_route = rib_ipv4_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route1)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route1, 'zebra')

    # Verify route 143.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route2["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route2)
    aux_route = rib_ipv4_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route2)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route2, 'zebra')

    # Verify route 163.0.0.1/32 and next-hops in RIB and FIB
    aux_route = route_ipv4_static_route3["Route"]
    verify_show_ip_route(sw1, aux_route, 'static', route_ipv4_static_route3)
    aux_route = rib_ipv4_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv4_static_route3)
    verify_route_in_show_kernel_route(sw1, True,
                                      route_ipv4_kernel_route3, 'zebra')

    step("Verifying the IPv6 static routes on switch 1")

    # Verify route a234:a234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route1["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route1)
    aux_route = rib_ipv6_static_route1["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route1)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route1, 'zebra')

    # Verify route 2234:2234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route2["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route2)
    aux_route = rib_ipv6_static_route2["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route2)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route2, 'zebra')

    # Verify route 3234:3234::1/128 and next-hops in RIB and FIB
    aux_route = route_ipv6_static_route3["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'static', route_ipv6_static_route3)
    aux_route = rib_ipv6_static_route3["Route"]
    verify_show_rib(sw1, aux_route, 'static', rib_ipv6_static_route3)
    verify_route_in_show_kernel_route(sw1, False,
                                      route_ipv6_kernel_route3, 'zebra')


@mark.timeout(ZEBRA_DEFAULT_TIMEOUT)
@mark.gate
def test_zebra_ct_restartability(topology, step):
    sw1 = topology.get("sw1")
    sw2 = topology.get("sw2")

    assert sw1 is not None
    assert sw2 is not None

    configure_static_routes(sw1, sw2, step)
    restart_zebra_without_config_change(sw1, sw2, step)
    restart_zebra_with_config_change(sw1, sw2, step)
    config_change_after_zebra_restart(sw1, sw2, step)
    interface_down_before_zebra_restart(sw1, sw2, step)
    interface_up_before_zebra_restart(sw1, sw2, step)
    interface_addr_change_before_zebra_restart(sw1, sw2, step)
    interface_addr_restore_before_zebra_restart(sw1, sw2, step)
    all_configuration_deleted_before_zebra_restart(sw1, sw2, step)
