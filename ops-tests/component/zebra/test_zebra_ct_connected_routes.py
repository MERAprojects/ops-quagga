# -*- coding: utf-8 -*-
#
# (c)Copyright 2015 Hewlett Packard Enterprise Development LP
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


from helpers_routing import (
    ZEBRA_TEST_SLEEP_TIME,
    ZEBRA_INIT_SLEEP_TIME,
    verify_show_ip_route,
    verify_show_ipv6_route,
    verify_show_rib
)
from time import sleep


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

# This test configures IPv4 and IPv6 interface addresses on different interface
# types and check if the corresponding connected routes have been programmed in FIB
# by looking into the output of "show ip/ipv6 route/show rib".
def configure_layer3_interfaces(sw1, sw2, step):

    # Configure physical layer-3 interface
    sw1_interface = sw1.ports["if0{}".format(1)]

    sw1("configure terminal")
    sw1("interface {}".format(sw1_interface))
    sw1("ip address 1.1.1.1/24")
    sw1("ip address 11.11.11.11/24 secondary")
    sw1("ipv6 address 1:1::1/64")
    sw1("ipv6 address 11:11::11/64 secondary")
    sw1("no shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    rib_ipv4_layer3_connected_route_primary = dict()
    rib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'
    rib_ipv4_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_primary['1'] = dict()
    rib_ipv4_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    fib_ipv4_layer3_connected_route_primary = rib_ipv4_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 secondary address and its next-hops.
    rib_ipv4_layer3_connected_route_secondary = dict()
    rib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'
    rib_ipv4_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_secondary['1'] = dict()
    rib_ipv4_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 secndary  address and its next-hops.
    fib_ipv4_layer3_connected_route_secondary = rib_ipv4_layer3_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    rib_ipv6_layer3_connected_route_primary = dict()
    rib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'
    rib_ipv6_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_primary['1'] = dict()
    rib_ipv6_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    fib_ipv6_layer3_connected_route_primary = rib_ipv6_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 secondary address and its next-hops.
    rib_ipv6_layer3_connected_route_secondary = dict()
    rib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'
    rib_ipv6_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_secondary['1'] = dict()
    rib_ipv6_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 secondary  address and its next-hops.
    fib_ipv6_layer3_connected_route_secondary = rib_ipv6_layer3_connected_route_secondary

    # Configure a Vlan interface
    sw1("configure terminal")
    sw1("vlan 100")
    sw1("no shutdown")
    sw1("exit")

    sw1_interface = sw1.ports["if0{}".format(2)]

    sw1("configure terminal")
    sw1("interface {}".format(sw1_interface))
    sw1("no routing")
    sw1("no shutdown")
    sw1("vlan access 100")
    sw1("exit")

    sw1("configure terminal")
    sw1("interface vlan 100")
    sw1("ip address 2.2.2.2/24")
    sw1("ipv6 address 2:2::2/64")
    sw1("ip address 22.22.22.22/24 secondary")
    sw1("ipv6 address 22:22::22/64 secondary")
    sw1("no shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    rib_ipv4_vlan_connected_route_primary = dict()
    rib_ipv4_vlan_connected_route_primary['Route'] = '2.2.2.0/24'
    rib_ipv4_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    fib_ipv4_vlan_connected_route_primary = rib_ipv4_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan secondary address and its next-hops.
    rib_ipv4_vlan_connected_route_secondary = dict()
    rib_ipv4_vlan_connected_route_secondary['Route'] = '22.22.22.0/24'
    rib_ipv4_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan secondary  address and its next-hops.
    fib_ipv4_vlan_connected_route_secondary = rib_ipv4_vlan_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    rib_ipv6_vlan_connected_route_primary = dict()
    rib_ipv6_vlan_connected_route_primary['Route'] = '2:2::/64'
    rib_ipv6_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    fib_ipv6_vlan_connected_route_primary = rib_ipv6_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan secondary address and its next-hops.
    rib_ipv6_vlan_connected_route_secondary = dict()
    rib_ipv6_vlan_connected_route_secondary['Route'] = '22:22::/64'
    rib_ipv6_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan secondary  address and its next-hops.
    fib_ipv6_vlan_connected_route_secondary = rib_ipv6_vlan_connected_route_secondary

    # Configure an L3 subinterface

    # Configure the parent interface
    sw1_interface = sw1.ports["if0{}".format(3)]

    sw1("configure terminal")
    sw1("interface {}".format(sw1_interface))
    sw1("no shutdown")
    sw1("exit")

    # Configure the sub-interface. Secondary IP addresses are not supported within
    # L3 sub-interface.
    sw1("configure terminal")
    sw1("interface 3.1")
    sw1("encapsulation dot1Q 2")
    sw1("ip address 3.3.3.3/24")
    sw1("ipv6 address 3:3::3/64")
    sw1("no shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    rib_ipv4_subinterface_connected_route_primary = dict()
    rib_ipv4_subinterface_connected_route_primary['Route'] = '3.3.3.0/24'
    rib_ipv4_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv4_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    fib_ipv4_subinterface_connected_route_primary = rib_ipv4_subinterface_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    rib_ipv6_subinterface_connected_route_primary = dict()
    rib_ipv6_subinterface_connected_route_primary['Route'] = '3:3::/64'
    rib_ipv6_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv6_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_subinterface_connected_route_primary = rib_ipv6_subinterface_connected_route_primary

    # Configure a L3 loopback interface. Secondary IP addresses are not supported on
    # L3 loopback interfaces.
    sw1("configure terminal")
    sw1("interface loopback 1")
    sw1("ip address 4.4.4.4/24")
    sw1("ipv6 address 4:4::4/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    rib_ipv4_loopback_connected_route_primary = dict()
    rib_ipv4_loopback_connected_route_primary['Route'] = '4.4.4.0/24'
    rib_ipv4_loopback_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_loopback_connected_route_primary['loopback1'] = dict()
    rib_ipv4_loopback_connected_route_primary['loopback1']['Distance'] = '0'
    rib_ipv4_loopback_connected_route_primary['loopback1']['Metric'] = '0'
    rib_ipv4_loopback_connected_route_primary['loopback1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    fib_ipv4_loopback_connected_route_primary = rib_ipv4_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for loopback primary address and its next-hops.
    rib_ipv6_loopback_connected_route_primary = dict()
    rib_ipv6_loopback_connected_route_primary['Route'] = '4:4::/64'
    rib_ipv6_loopback_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_loopback_connected_route_primary['loopback1'] = dict()
    rib_ipv6_loopback_connected_route_primary['loopback1']['Distance'] = '0'
    rib_ipv6_loopback_connected_route_primary['loopback1']['Metric'] = '0'
    rib_ipv6_loopback_connected_route_primary['loopback1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_loopback_connected_route_primary = rib_ipv6_loopback_connected_route_primary

    # Configure a L3 LAG interface.
    sw1("configure terminal")
    sw1("interface lag 100")
    sw1("ip address 5.5.5.5/24")
    sw1("ip address 55.55.55.55/24 secondary")
    sw1("ipv6 address 5:5::5/64")
    sw1("ipv6 address 55:55::55/64 secondary")
    sw1("no shutdown")
    sw1("exit")

    # Configure the parent interface
    sw1_interface = sw1.ports["if0{}".format(4)]

    sw1("configure terminal")
    sw1("interface {}".format(sw1_interface))
    sw1("lag 100")
    sw1("no shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    rib_ipv4_lag_connected_route_primary = dict()
    rib_ipv4_lag_connected_route_primary['Route'] = '5.5.5.0/24'
    rib_ipv4_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_primary['lag100'] = dict()
    rib_ipv4_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    fib_ipv4_lag_connected_route_primary = rib_ipv4_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    rib_ipv4_lag_connected_route_secondary = dict()
    rib_ipv4_lag_connected_route_secondary['Route'] = '55.55.55.0/24'
    rib_ipv4_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv4_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    fib_ipv4_lag_connected_route_secondary = rib_ipv4_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    rib_ipv6_lag_connected_route_primary = dict()
    rib_ipv6_lag_connected_route_primary['Route'] = '5:5::/64'
    rib_ipv6_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_primary['lag100'] = dict()
    rib_ipv6_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    fib_ipv6_lag_connected_route_primary = rib_ipv6_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG secondary address and its next-hops.
    rib_ipv6_lag_connected_route_secondary = dict()
    rib_ipv6_lag_connected_route_secondary['Route'] = '55:55::/64'
    rib_ipv6_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv6_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG secndary address and its next-hops.
    fib_ipv6_lag_connected_route_secondary = rib_ipv6_lag_connected_route_secondary

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4/IPv6 connected routes on switch 1")

    # Verify IPv4 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_primary)
    aux_route = rib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_layer3_connected_route_primary)

    # Verify IPv4 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_secondary)
    aux_route = rib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_layer3_connected_route_secondary)

    # Verify IPv6 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_primary)
    aux_route = rib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_layer3_connected_route_primary)

    # Verify IPv6 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_secondary)
    aux_route = rib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_layer3_connected_route_secondary)

    # Verify IPv4 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_primary)
    aux_route = rib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_vlan_connected_route_primary)

    # Verify IPv4 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_secondary)
    aux_route = rib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_vlan_connected_route_secondary)

    # Verify IPv6 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_primary)
    aux_route = rib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_vlan_connected_route_primary)

    # Verify IPv6 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_secondary)
    aux_route = rib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_vlan_connected_route_secondary)

    # Verify IPv4 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_subinterface_connected_route_primary)
    aux_route = rib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_subinterface_connected_route_primary)

    # Verify IPv6 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_subinterface_connected_route_primary)
    aux_route = rib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_subinterface_connected_route_primary)

    # Verify IPv4 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_loopback_connected_route_primary)
    aux_route = rib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_loopback_connected_route_primary)

    # Verify IPv6 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_loopback_connected_route_primary)
    aux_route = rib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_loopback_connected_route_primary)

    # Verify IPv4 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_primary)
    aux_route = rib_ipv4_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_lag_connected_route_primary)

    # Verify IPv4 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_secondary)
    aux_route = rib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_lag_connected_route_secondary)

    # Verify IPv6 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_primary)
    aux_route = rib_ipv6_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_lag_connected_route_primary)

    # Verify IPv6 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_secondary)
    aux_route = rib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_lag_connected_route_secondary)


# This test shuts down IPv4 and IPv6 interfaces and check if the corresponding
# connected routes have been withdrawn from FIB by looking into the output of
# "show ip/ipv6 route/show rib".
def shutdown_layer3_interfaces(sw1, sw2, step):

    # Shutdown layer-3 interface
    sw1("configure terminal")
    sw1("interface 1")
    sw1("shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    rib_ipv4_layer3_connected_route_primary = dict()
    rib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'
    rib_ipv4_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_primary['1'] = dict()
    rib_ipv4_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    fib_ipv4_layer3_connected_route_primary = dict()
    fib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 secondary address and its next-hops.
    rib_ipv4_layer3_connected_route_secondary = dict()
    rib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'
    rib_ipv4_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_secondary['1'] = dict()
    rib_ipv4_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 secndary  address and its next-hops.
    fib_ipv4_layer3_connected_route_secondary = dict()
    fib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    rib_ipv6_layer3_connected_route_primary = dict()
    rib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'
    rib_ipv6_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_primary['1'] = dict()
    rib_ipv6_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    fib_ipv6_layer3_connected_route_primary = dict()
    fib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 secondary address and its next-hops.
    rib_ipv6_layer3_connected_route_secondary = dict()
    rib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'
    rib_ipv6_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_secondary['1'] = dict()
    rib_ipv6_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 secondary  address and its next-hops.
    fib_ipv6_layer3_connected_route_secondary = dict()
    fib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'

    # Shutdown the vlan interface
    sw1("configure terminal")
    sw1("interface vlan 100")
    sw1("shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    rib_ipv4_vlan_connected_route_primary = dict()
    rib_ipv4_vlan_connected_route_primary['Route'] = '2.2.2.0/24'
    rib_ipv4_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    fib_ipv4_vlan_connected_route_primary = dict()
    fib_ipv4_vlan_connected_route_primary['Route'] = '2.2.2.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan secondary address and its next-hops.
    rib_ipv4_vlan_connected_route_secondary = dict()
    rib_ipv4_vlan_connected_route_secondary['Route'] = '22.22.22.0/24'
    rib_ipv4_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan secondary  address and its next-hops.
    fib_ipv4_vlan_connected_route_secondary = dict()
    fib_ipv4_vlan_connected_route_secondary['Route'] = '22.22.22.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    rib_ipv6_vlan_connected_route_primary = dict()
    rib_ipv6_vlan_connected_route_primary['Route'] = '2:2::/64'
    rib_ipv6_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    fib_ipv6_vlan_connected_route_primary = dict()
    fib_ipv6_vlan_connected_route_primary['Route'] = '2:2::/64'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan secondary address and its next-hops.
    rib_ipv6_vlan_connected_route_secondary = dict()
    rib_ipv6_vlan_connected_route_secondary['Route'] = '22:22::/64'
    rib_ipv6_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan secondary  address and its next-hops.
    fib_ipv6_vlan_connected_route_secondary = dict()
    fib_ipv6_vlan_connected_route_secondary['Route'] = '22:22::/64'

    # Shutdown the L3 sub-interface.
    sw1("configure terminal")
    sw1("interface 3.1")
    sw1("no encapsulation dot1Q 2")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    rib_ipv4_subinterface_connected_route_primary = dict()
    rib_ipv4_subinterface_connected_route_primary['Route'] = '3.3.3.0/24'
    rib_ipv4_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv4_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    fib_ipv4_subinterface_connected_route_primary = dict()
    fib_ipv4_subinterface_connected_route_primary['Route'] = '3.3.3.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    rib_ipv6_subinterface_connected_route_primary = dict()
    rib_ipv6_subinterface_connected_route_primary['Route'] = '3:3::/64'
    rib_ipv6_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv6_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_subinterface_connected_route_primary = dict()
    fib_ipv6_subinterface_connected_route_primary['Route'] = '3:3::/64'

    # We cannot toggle(shut/no shut) loopback interface. So skip populating the
    # verification dictionaries for loopback interface.

    # Shutdown the L3 LAG interface.
    sw1("configure terminal")
    sw1("interface lag 100")
    sw1("shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    rib_ipv4_lag_connected_route_primary = dict()
    rib_ipv4_lag_connected_route_primary['Route'] = '5.5.5.0/24'
    rib_ipv4_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_primary['lag100'] = dict()
    rib_ipv4_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    fib_ipv4_lag_connected_route_primary = dict()
    fib_ipv4_lag_connected_route_primary['Route'] = '5.5.5.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    rib_ipv4_lag_connected_route_secondary = dict()
    rib_ipv4_lag_connected_route_secondary['Route'] = '55.55.55.0/24'
    rib_ipv4_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv4_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    fib_ipv4_lag_connected_route_secondary = dict()
    fib_ipv4_lag_connected_route_secondary['Route'] = '55.55.55.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    rib_ipv6_lag_connected_route_primary = dict()
    rib_ipv6_lag_connected_route_primary['Route'] = '5:5::/64'
    rib_ipv6_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_primary['lag100'] = dict()
    rib_ipv6_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    fib_ipv6_lag_connected_route_primary = dict()
    fib_ipv6_lag_connected_route_primary['Route'] = '5:5::/64'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG secondary address and its next-hops.
    rib_ipv6_lag_connected_route_secondary = dict()
    rib_ipv6_lag_connected_route_secondary['Route'] = '55:55::/64'
    rib_ipv6_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv6_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG secndary address and its next-hops.
    fib_ipv6_lag_connected_route_secondary = dict()
    fib_ipv6_lag_connected_route_secondary['Route'] = '55:55::/64'

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4/IPv6 connected routes on switch 1")

    # Verify IPv4 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_primary)
    aux_route = rib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_layer3_connected_route_primary)

    # Verify IPv4 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_secondary)
    aux_route = rib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_layer3_connected_route_secondary)

    # Verify IPv6 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_primary)
    aux_route = rib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_layer3_connected_route_primary)

    # Verify IPv6 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_secondary)
    aux_route = rib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_layer3_connected_route_secondary)

    # Verify IPv4 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_primary)
    aux_route = rib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_vlan_connected_route_primary)

    # Verify IPv4 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_secondary)
    aux_route = rib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_vlan_connected_route_secondary)

    # Verify IPv6 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_primary)
    aux_route = rib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_vlan_connected_route_primary)

    # Verify IPv6 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_secondary)
    aux_route = rib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_vlan_connected_route_secondary)

    # Verify IPv4 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_subinterface_connected_route_primary)
    aux_route = rib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_subinterface_connected_route_primary)

    # Verify IPv6 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_subinterface_connected_route_primary)
    aux_route = rib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_subinterface_connected_route_primary)

    # Verify IPv4 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_primary)
    aux_route = rib_ipv4_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_lag_connected_route_primary)

    # Verify IPv4 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_secondary)
    aux_route = rib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_lag_connected_route_secondary)

    # Verify IPv6 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_primary)
    aux_route = rib_ipv6_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_lag_connected_route_primary)

    # Verify IPv6 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_secondary)
    aux_route = rib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_lag_connected_route_secondary)


# This test brings up IPv4 and IPv6 interfaces and check if the corresponding
# connected routes have been reprogrammed into FIB by looking into the output of
# "show ip/ipv6 route/show rib".
def no_shutdown_layer3_interfaces(sw1, sw2, step):

    # Un-shutdown layer-3 interface
    sw1("configure terminal")
    sw1("interface 1")
    sw1("no shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    rib_ipv4_layer3_connected_route_primary = dict()
    rib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'
    rib_ipv4_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_primary['1'] = dict()
    rib_ipv4_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    fib_ipv4_layer3_connected_route_primary = rib_ipv4_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 secondary address and its next-hops.
    rib_ipv4_layer3_connected_route_secondary = dict()
    rib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'
    rib_ipv4_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_secondary['1'] = dict()
    rib_ipv4_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 secndary  address and its next-hops.
    fib_ipv4_layer3_connected_route_secondary = rib_ipv4_layer3_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    rib_ipv6_layer3_connected_route_primary = dict()
    rib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'
    rib_ipv6_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_primary['1'] = dict()
    rib_ipv6_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    fib_ipv6_layer3_connected_route_primary = rib_ipv6_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 secondary address and its next-hops.
    rib_ipv6_layer3_connected_route_secondary = dict()
    rib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'
    rib_ipv6_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_secondary['1'] = dict()
    rib_ipv6_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 secondary  address and its next-hops.
    fib_ipv6_layer3_connected_route_secondary = rib_ipv6_layer3_connected_route_secondary

    # Un-shutdown the vlan interface
    sw1("configure terminal")
    sw1("interface vlan 100")
    sw1("no shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    rib_ipv4_vlan_connected_route_primary = dict()
    rib_ipv4_vlan_connected_route_primary['Route'] = '2.2.2.0/24'
    rib_ipv4_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    fib_ipv4_vlan_connected_route_primary = rib_ipv4_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan secondary address and its next-hops.
    rib_ipv4_vlan_connected_route_secondary = dict()
    rib_ipv4_vlan_connected_route_secondary['Route'] = '22.22.22.0/24'
    rib_ipv4_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan secondary  address and its next-hops.
    fib_ipv4_vlan_connected_route_secondary = rib_ipv4_vlan_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    rib_ipv6_vlan_connected_route_primary = dict()
    rib_ipv6_vlan_connected_route_primary['Route'] = '2:2::/64'
    rib_ipv6_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    fib_ipv6_vlan_connected_route_primary = rib_ipv6_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan secondary address and its next-hops.
    rib_ipv6_vlan_connected_route_secondary = dict()
    rib_ipv6_vlan_connected_route_secondary['Route'] = '22:22::/64'
    rib_ipv6_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan secondary  address and its next-hops.
    fib_ipv6_vlan_connected_route_secondary = rib_ipv6_vlan_connected_route_secondary

    # Un-shutdown the L3 sub-interface.
    sw1("configure terminal")
    sw1("interface 3.1")
    sw1("encapsulation dot1Q 2")
    sw1("no shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    rib_ipv4_subinterface_connected_route_primary = dict()
    rib_ipv4_subinterface_connected_route_primary['Route'] = '3.3.3.0/24'
    rib_ipv4_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv4_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    fib_ipv4_subinterface_connected_route_primary = rib_ipv4_subinterface_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    rib_ipv6_subinterface_connected_route_primary = dict()
    rib_ipv6_subinterface_connected_route_primary['Route'] = '3:3::/64'
    rib_ipv6_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv6_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_subinterface_connected_route_primary = rib_ipv6_subinterface_connected_route_primary

    # We cannot toggle(shut/no shut) loopback interface. So skip populating the
    # verification dictionaries for loopback interface.

    # Un-shutdown the L3 LAG interface.
    sw1("configure terminal")
    sw1("interface lag 100")
    sw1("no shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    rib_ipv4_lag_connected_route_primary = dict()
    rib_ipv4_lag_connected_route_primary['Route'] = '5.5.5.0/24'
    rib_ipv4_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_primary['lag100'] = dict()
    rib_ipv4_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    fib_ipv4_lag_connected_route_primary = rib_ipv4_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    rib_ipv4_lag_connected_route_secondary = dict()
    rib_ipv4_lag_connected_route_secondary['Route'] = '55.55.55.0/24'
    rib_ipv4_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv4_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    fib_ipv4_lag_connected_route_secondary = rib_ipv4_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    rib_ipv6_lag_connected_route_primary = dict()
    rib_ipv6_lag_connected_route_primary['Route'] = '5:5::/64'
    rib_ipv6_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_primary['lag100'] = dict()
    rib_ipv6_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    fib_ipv6_lag_connected_route_primary = rib_ipv6_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG secondary address and its next-hops.
    rib_ipv6_lag_connected_route_secondary = dict()
    rib_ipv6_lag_connected_route_secondary['Route'] = '55:55::/64'
    rib_ipv6_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv6_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG secndary address and its next-hops.
    fib_ipv6_lag_connected_route_secondary = rib_ipv6_lag_connected_route_secondary

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4/IPv6 connected routes on switch 1")

    # Verify IPv4 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_primary)
    aux_route = rib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_layer3_connected_route_primary)

    # Verify IPv4 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_secondary)
    aux_route = rib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_layer3_connected_route_secondary)

    # Verify IPv6 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_primary)
    aux_route = rib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_layer3_connected_route_primary)

    # Verify IPv6 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_secondary)
    aux_route = rib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_layer3_connected_route_secondary)

    # Verify IPv4 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_primary)
    aux_route = rib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_vlan_connected_route_primary)

    # Verify IPv4 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_secondary)
    aux_route = rib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_vlan_connected_route_secondary)

    # Verify IPv6 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_primary)
    aux_route = rib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_vlan_connected_route_primary)

    # Verify IPv6 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_secondary)
    aux_route = rib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_vlan_connected_route_secondary)

    # Verify IPv4 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_subinterface_connected_route_primary)
    aux_route = rib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_subinterface_connected_route_primary)

    # Verify IPv6 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_subinterface_connected_route_primary)
    aux_route = rib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_subinterface_connected_route_primary)

    # Verify IPv4 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_primary)
    aux_route = rib_ipv4_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_lag_connected_route_primary)

    # Verify IPv4 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_secondary)
    aux_route = rib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_lag_connected_route_secondary)

    # Verify IPv6 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_primary)
    aux_route = rib_ipv6_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_lag_connected_route_primary)

    # Verify IPv6 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_secondary)
    aux_route = rib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_lag_connected_route_secondary)


# This test removes IPv4 and IPv6 interfaces addresses (both primary and secondary
# )and check if the corresponding connected routes have been removed from FIB and RIB
# by looking into the output of "show ip/ipv6 route/show rib".
def remove_addresses_from_layer3_interfaces(sw1, sw2, step):

    # Un-configure layer-3 interface addresses
    sw1("configure terminal")
    sw1("interface 1")
    sw1("no ip address 11.11.11.11/24 secondary")
    sw1("no ipv6 address 11:11::11/64 secondary")
    sw1("no ip address 1.1.1.1/24")
    sw1("no ipv6 address 1:1::1/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    rib_ipv4_layer3_connected_route_primary = dict()
    rib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    fib_ipv4_layer3_connected_route_primary = dict()
    fib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 secondary address and its next-hops.
    rib_ipv4_layer3_connected_route_secondary = dict()
    rib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 secndary  address and its next-hops.
    fib_ipv4_layer3_connected_route_secondary = dict()
    fib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    rib_ipv6_layer3_connected_route_primary = dict()
    rib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    fib_ipv6_layer3_connected_route_primary = dict()
    fib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 secondary address and its next-hops.
    rib_ipv6_layer3_connected_route_secondary = dict()
    rib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 secondary  address and its next-hops.
    fib_ipv6_layer3_connected_route_secondary = dict()
    fib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'

    # Un-configure vlan interface addresses
    sw1("configure terminal")
    sw1("interface vlan 100")
    sw1("no ip address 22.22.22.22/24 secondary")
    sw1("no ipv6 address 22:22::22/64 secondary")
    sw1("no ip address 2.2.2.2/24")
    sw1("no ipv6 address 2:2::2/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    rib_ipv4_vlan_connected_route_primary = dict()
    rib_ipv4_vlan_connected_route_primary['Route'] = '2.2.2.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    fib_ipv4_vlan_connected_route_primary = rib_ipv4_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan secondary address and its next-hops.
    rib_ipv4_vlan_connected_route_secondary = dict()
    rib_ipv4_vlan_connected_route_secondary['Route'] = '22.22.22.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan secondary  address and its next-hops.
    fib_ipv4_vlan_connected_route_secondary = rib_ipv4_vlan_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    rib_ipv6_vlan_connected_route_primary = dict()
    rib_ipv6_vlan_connected_route_primary['Route'] = '2:2::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    fib_ipv6_vlan_connected_route_primary = rib_ipv6_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan secondary address and its next-hops.
    rib_ipv6_vlan_connected_route_secondary = dict()
    rib_ipv6_vlan_connected_route_secondary['Route'] = '22:22::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan secondary  address and its next-hops.
    fib_ipv6_vlan_connected_route_secondary = rib_ipv6_vlan_connected_route_secondary

    # Un-configure L3 sub-interface interface addresses
    sw1("configure terminal")
    sw1("interface 3.1")
    sw1("no ip address 3.3.3.3/24")
    sw1("no ipv6 address 3:3::3/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    rib_ipv4_subinterface_connected_route_primary = dict()
    rib_ipv4_subinterface_connected_route_primary['Route'] = '3.3.3.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    fib_ipv4_subinterface_connected_route_primary = rib_ipv4_subinterface_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    rib_ipv6_subinterface_connected_route_primary = dict()
    rib_ipv6_subinterface_connected_route_primary['Route'] = '3:3::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_subinterface_connected_route_primary = rib_ipv6_subinterface_connected_route_primary

    # Un-configure loopback interface addresses
    sw1("configure terminal")
    sw1("interface loopback 1")
    sw1("no ip address 4.4.4.4/24")
    sw1("no ipv6 address 4:4::4/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    rib_ipv4_loopback_connected_route_primary = dict()
    rib_ipv4_loopback_connected_route_primary['Route'] = '4.4.4.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    fib_ipv4_loopback_connected_route_primary = rib_ipv4_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for loopback primary address and its next-hops.
    rib_ipv6_loopback_connected_route_primary = dict()
    rib_ipv6_loopback_connected_route_primary['Route'] = '4:4::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_loopback_connected_route_primary = rib_ipv6_loopback_connected_route_primary

    # Un-configure L3 lag interface addresses
    sw1("configure terminal")
    sw1("interface lag 100")
    sw1("no ip address 55.55.55.55/24 secondary")
    sw1("no ipv6 address 55:55::55/64 secondary")
    sw1("no ip address 5.5.5.5/24")
    sw1("no ipv6 address 5:5::5/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    rib_ipv4_lag_connected_route_primary = dict()
    rib_ipv4_lag_connected_route_primary['Route'] = '5.5.5.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    fib_ipv4_lag_connected_route_primary = rib_ipv4_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    rib_ipv4_lag_connected_route_secondary = dict()
    rib_ipv4_lag_connected_route_secondary['Route'] = '55.55.55.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    fib_ipv4_lag_connected_route_secondary = rib_ipv4_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    rib_ipv6_lag_connected_route_primary = dict()
    rib_ipv6_lag_connected_route_primary['Route'] = '5:5::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    fib_ipv6_lag_connected_route_primary = rib_ipv6_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG secondary address and its next-hops.
    rib_ipv6_lag_connected_route_secondary = dict()
    rib_ipv6_lag_connected_route_secondary['Route'] = '55:55::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG secndary address and its next-hops.
    fib_ipv6_lag_connected_route_secondary = rib_ipv6_lag_connected_route_secondary

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4/IPv6 connected routes on switch 1")

    # Verify IPv4 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_primary)
    aux_route = rib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_layer3_connected_route_primary)

    # Verify IPv4 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_secondary)
    aux_route = rib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_layer3_connected_route_secondary)

    # Verify IPv6 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_primary)
    aux_route = rib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_layer3_connected_route_primary)

    # Verify IPv6 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_secondary)
    aux_route = rib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_layer3_connected_route_secondary)

    # Verify IPv4 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_primary)
    aux_route = rib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_vlan_connected_route_primary)

    # Verify IPv4 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_secondary)
    aux_route = rib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_vlan_connected_route_secondary)

    # Verify IPv6 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_primary)
    aux_route = rib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_vlan_connected_route_primary)

    # Verify IPv6 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_secondary)
    aux_route = rib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_vlan_connected_route_secondary)

    # Verify IPv4 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_subinterface_connected_route_primary)
    aux_route = rib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_subinterface_connected_route_primary)

    # Verify IPv6 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_subinterface_connected_route_primary)
    aux_route = rib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_subinterface_connected_route_primary)

    # Verify IPv4 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_loopback_connected_route_primary)
    aux_route = rib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_loopback_connected_route_primary)

    # Verify IPv6 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_loopback_connected_route_primary)
    aux_route = rib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_loopback_connected_route_primary)

    # Verify IPv4 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_primary)
    aux_route = rib_ipv4_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_lag_connected_route_primary)

    # Verify IPv4 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_secondary)
    aux_route = rib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_lag_connected_route_secondary)

    # Verify IPv6 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_primary)
    aux_route = rib_ipv6_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_lag_connected_route_primary)

    # Verify IPv6 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_secondary)
    aux_route = rib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_lag_connected_route_secondary)


# This test adds back IPv4 and IPv6 interfaces addresses (both primary and secondary
# )and check if the corresponding connected routes have been added into FIB and RIB
# by looking into the output of "show ip/ipv6 route/show rib".
def reconfigure_addresses_on_layer3_interfaces(sw1, sw2, step):

    # Re-configure layer-3 interface addresses
    sw1("configure terminal")
    sw1("interface 1")
    sw1("ip address 1.1.1.1/24")
    sw1("ipv6 address 1:1::1/64")
    sw1("ip address 11.11.11.11/24 secondary")
    sw1("ipv6 address 11:11::11/64 secondary")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    rib_ipv4_layer3_connected_route_primary = dict()
    rib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'
    rib_ipv4_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_primary['1'] = dict()
    rib_ipv4_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    fib_ipv4_layer3_connected_route_primary = rib_ipv4_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 secondary address and its next-hops.
    rib_ipv4_layer3_connected_route_secondary = dict()
    rib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'
    rib_ipv4_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_secondary['1'] = dict()
    rib_ipv4_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 secndary  address and its next-hops.
    fib_ipv4_layer3_connected_route_secondary = rib_ipv4_layer3_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    rib_ipv6_layer3_connected_route_primary = dict()
    rib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'
    rib_ipv6_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_primary['1'] = dict()
    rib_ipv6_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    fib_ipv6_layer3_connected_route_primary = rib_ipv6_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 secondary address and its next-hops.
    rib_ipv6_layer3_connected_route_secondary = dict()
    rib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'
    rib_ipv6_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_secondary['1'] = dict()
    rib_ipv6_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 secondary  address and its next-hops.
    fib_ipv6_layer3_connected_route_secondary = rib_ipv6_layer3_connected_route_secondary

    # Re-configure vlan interface addresses
    sw1("configure terminal")
    sw1("interface vlan 100")
    sw1("ip address 22.22.22.22/24 secondary")
    sw1("ipv6 address 22:22::22/64 secondary")
    sw1("ip address 2.2.2.2/24")
    sw1("ipv6 address 2:2::2/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    rib_ipv4_vlan_connected_route_primary = dict()
    rib_ipv4_vlan_connected_route_primary['Route'] = '2.2.2.0/24'
    rib_ipv4_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    fib_ipv4_vlan_connected_route_primary = rib_ipv4_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan secondary address and its next-hops.
    rib_ipv4_vlan_connected_route_secondary = dict()
    rib_ipv4_vlan_connected_route_secondary['Route'] = '22.22.22.0/24'
    rib_ipv4_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan secondary  address and its next-hops.
    fib_ipv4_vlan_connected_route_secondary = rib_ipv4_vlan_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    rib_ipv6_vlan_connected_route_primary = dict()
    rib_ipv6_vlan_connected_route_primary['Route'] = '2:2::/64'
    rib_ipv6_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    fib_ipv6_vlan_connected_route_primary = rib_ipv6_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan secondary address and its next-hops.
    rib_ipv6_vlan_connected_route_secondary = dict()
    rib_ipv6_vlan_connected_route_secondary['Route'] = '22:22::/64'
    rib_ipv6_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan secondary  address and its next-hops.
    fib_ipv6_vlan_connected_route_secondary = rib_ipv6_vlan_connected_route_secondary

    # Re-configure L3 sub-interface interface addresses
    sw1("configure terminal")
    sw1("interface 3.1")
    sw1("ip address 3.3.3.3/24")
    sw1("ipv6 address 3:3::3/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    rib_ipv4_subinterface_connected_route_primary = dict()
    rib_ipv4_subinterface_connected_route_primary['Route'] = '3.3.3.0/24'
    rib_ipv4_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv4_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    fib_ipv4_subinterface_connected_route_primary = rib_ipv4_subinterface_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    rib_ipv6_subinterface_connected_route_primary = dict()
    rib_ipv6_subinterface_connected_route_primary['Route'] = '3:3::/64'
    rib_ipv6_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv6_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_subinterface_connected_route_primary = rib_ipv6_subinterface_connected_route_primary

    # Re-configure loopback interface addresses
    sw1("configure terminal")
    sw1("interface loopback 1")
    sw1("ip address 4.4.4.4/24")
    sw1("ipv6 address 4:4::4/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    rib_ipv4_loopback_connected_route_primary = dict()
    rib_ipv4_loopback_connected_route_primary['Route'] = '4.4.4.0/24'
    rib_ipv4_loopback_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_loopback_connected_route_primary['loopback1'] = dict()
    rib_ipv4_loopback_connected_route_primary['loopback1']['Distance'] = '0'
    rib_ipv4_loopback_connected_route_primary['loopback1']['Metric'] = '0'
    rib_ipv4_loopback_connected_route_primary['loopback1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    fib_ipv4_loopback_connected_route_primary = rib_ipv4_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for loopback primary address and its next-hops.
    rib_ipv6_loopback_connected_route_primary = dict()
    rib_ipv6_loopback_connected_route_primary['Route'] = '4:4::/64'
    rib_ipv6_loopback_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_loopback_connected_route_primary['loopback1'] = dict()
    rib_ipv6_loopback_connected_route_primary['loopback1']['Distance'] = '0'
    rib_ipv6_loopback_connected_route_primary['loopback1']['Metric'] = '0'
    rib_ipv6_loopback_connected_route_primary['loopback1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_loopback_connected_route_primary = rib_ipv6_loopback_connected_route_primary

    # Re-configure L3 lag interface addresses
    sw1("configure terminal")
    sw1("interface lag 100")
    sw1("ip address 5.5.5.5/24")
    sw1("ipv6 address 5:5::5/64")
    sw1("ip address 55.55.55.55/24 secondary")
    sw1("ipv6 address 55:55::55/64 secondary")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    rib_ipv4_lag_connected_route_primary = dict()
    rib_ipv4_lag_connected_route_primary['Route'] = '5.5.5.0/24'
    rib_ipv4_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_primary['lag100'] = dict()
    rib_ipv4_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    fib_ipv4_lag_connected_route_primary = rib_ipv4_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    rib_ipv4_lag_connected_route_secondary = dict()
    rib_ipv4_lag_connected_route_secondary['Route'] = '55.55.55.0/24'
    rib_ipv4_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv4_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    fib_ipv4_lag_connected_route_secondary = rib_ipv4_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    rib_ipv6_lag_connected_route_primary = dict()
    rib_ipv6_lag_connected_route_primary['Route'] = '5:5::/64'
    rib_ipv6_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_primary['lag100'] = dict()
    rib_ipv6_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    fib_ipv6_lag_connected_route_primary = rib_ipv6_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG secondary address and its next-hops.
    rib_ipv6_lag_connected_route_secondary = dict()
    rib_ipv6_lag_connected_route_secondary['Route'] = '55:55::/64'
    rib_ipv6_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv6_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG secndary address and its next-hops.
    fib_ipv6_lag_connected_route_secondary = rib_ipv6_lag_connected_route_secondary

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4/IPv6 connected routes on switch 1")

    # Verify IPv4 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_primary)
    aux_route = rib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_layer3_connected_route_primary)

    # Verify IPv4 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_secondary)
    aux_route = rib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_layer3_connected_route_secondary)

    # Verify IPv6 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_primary)
    aux_route = rib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_layer3_connected_route_primary)

    # Verify IPv6 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_secondary)
    aux_route = rib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_layer3_connected_route_secondary)

    # Verify IPv4 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_primary)
    aux_route = rib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_vlan_connected_route_primary)

    # Verify IPv4 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_secondary)
    aux_route = rib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_vlan_connected_route_secondary)

    # Verify IPv6 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_primary)
    aux_route = rib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_vlan_connected_route_primary)

    # Verify IPv6 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_secondary)
    aux_route = rib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_vlan_connected_route_secondary)

    # Verify IPv4 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_subinterface_connected_route_primary)
    aux_route = rib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_subinterface_connected_route_primary)

    # Verify IPv6 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_subinterface_connected_route_primary)
    aux_route = rib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_subinterface_connected_route_primary)

    # Verify IPv4 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_loopback_connected_route_primary)
    aux_route = rib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_loopback_connected_route_primary)

    # Verify IPv6 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_loopback_connected_route_primary)
    aux_route = rib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_loopback_connected_route_primary)

    # Verify IPv4 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_primary)
    aux_route = rib_ipv4_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_lag_connected_route_primary)

    # Verify IPv4 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_secondary)
    aux_route = rib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_lag_connected_route_secondary)

    # Verify IPv6 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_primary)
    aux_route = rib_ipv6_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_lag_connected_route_primary)

    # Verify IPv6 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_secondary)
    aux_route = rib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_lag_connected_route_secondary)


# This test case shuts down zebra process and then changes some L3 interface
# configuration. The test case then brings up the zebra process and tests if
# with the new L3 interface configuration, the zebra process cleans or programs
# OVSDB correctly for the connected routes. We test the connected routes using
# the output of "show ip/ipv6 route/show rib".
def restart_zebra_with_config_change_for_layer3_interfaces(sw1, sw2, step):

    step("Stopping the ops-zebra process on switch 1")

    # Stop ops-zebra process on sw1
    sw1(zebra_stop_command_string, shell='bash')

    # Change configuration for Layer-3 interface by shutting down the interface
    sw1("configure terminal")
    sw1("interface 1")
    sw1("shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    rib_ipv4_layer3_connected_route_primary = dict()
    rib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'
    rib_ipv4_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_primary['1'] = dict()
    rib_ipv4_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    fib_ipv4_layer3_connected_route_primary = dict()
    fib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 secondary address and its next-hops.
    rib_ipv4_layer3_connected_route_secondary = dict()
    rib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'
    rib_ipv4_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_secondary['1'] = dict()
    rib_ipv4_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 secndary  address and its next-hops.
    fib_ipv4_layer3_connected_route_secondary = dict()
    fib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    rib_ipv6_layer3_connected_route_primary = dict()
    rib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'
    rib_ipv6_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_primary['1'] = dict()
    rib_ipv6_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    fib_ipv6_layer3_connected_route_primary = dict()
    fib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 secondary address and its next-hops.
    rib_ipv6_layer3_connected_route_secondary = dict()
    rib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'
    rib_ipv6_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_secondary['1'] = dict()
    rib_ipv6_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 secondary  address and its next-hops.
    fib_ipv6_layer3_connected_route_secondary = dict()
    fib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'

    # Change configuration for Vlan interface by removing all primary and
    # secondary IPv4 and IPV6 addresses.
    sw1("configure terminal")
    sw1("interface vlan 100")
    sw1("no ip address 22.22.22.22/24 secondary")
    sw1("no ipv6 address 22:22::22/64 secondary")
    sw1("no ip address 2.2.2.2/24")
    sw1("no ipv6 address 2:2::2/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    rib_ipv4_vlan_connected_route_primary = dict()
    rib_ipv4_vlan_connected_route_primary['Route'] = '2.2.2.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    fib_ipv4_vlan_connected_route_primary = rib_ipv4_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan secondary address and its next-hops.
    rib_ipv4_vlan_connected_route_secondary = dict()
    rib_ipv4_vlan_connected_route_secondary['Route'] = '22.22.22.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan secondary  address and its next-hops.
    fib_ipv4_vlan_connected_route_secondary = rib_ipv4_vlan_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    rib_ipv6_vlan_connected_route_primary = dict()
    rib_ipv6_vlan_connected_route_primary['Route'] = '2:2::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    fib_ipv6_vlan_connected_route_primary = rib_ipv6_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan secondary address and its next-hops.
    rib_ipv6_vlan_connected_route_secondary = dict()
    rib_ipv6_vlan_connected_route_secondary['Route'] = '22:22::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan secondary  address and its next-hops.
    fib_ipv6_vlan_connected_route_secondary = rib_ipv6_vlan_connected_route_secondary

    # Do not change the configuration for the L3 sub-interface

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    rib_ipv4_subinterface_connected_route_primary = dict()
    rib_ipv4_subinterface_connected_route_primary['Route'] = '3.3.3.0/24'
    rib_ipv4_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv4_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    fib_ipv4_subinterface_connected_route_primary = rib_ipv4_subinterface_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    rib_ipv6_subinterface_connected_route_primary = dict()
    rib_ipv6_subinterface_connected_route_primary['Route'] = '3:3::/64'
    rib_ipv6_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv6_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_subinterface_connected_route_primary = rib_ipv6_subinterface_connected_route_primary

    # Change the IPv4 and IPv6 addresses on the loopback interface
    sw1("configure terminal")
    sw1("interface loopback 1")
    sw1("ip address 6.6.6.6/24")
    sw1("ipv6 address 6:6::6/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    rib_ipv4_loopback_connected_route_primary = dict()
    rib_ipv4_loopback_connected_route_primary['Route'] = '6.6.6.0/24'
    rib_ipv4_loopback_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_loopback_connected_route_primary['loopback1'] = dict()
    rib_ipv4_loopback_connected_route_primary['loopback1']['Distance'] = '0'
    rib_ipv4_loopback_connected_route_primary['loopback1']['Metric'] = '0'
    rib_ipv4_loopback_connected_route_primary['loopback1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    fib_ipv4_loopback_connected_route_primary = rib_ipv4_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for loopback primary address and its next-hops.
    rib_ipv6_loopback_connected_route_primary = dict()
    rib_ipv6_loopback_connected_route_primary['Route'] = '6:6::/64'
    rib_ipv6_loopback_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_loopback_connected_route_primary['loopback1'] = dict()
    rib_ipv6_loopback_connected_route_primary['loopback1']['Distance'] = '0'
    rib_ipv6_loopback_connected_route_primary['loopback1']['Metric'] = '0'
    rib_ipv6_loopback_connected_route_primary['loopback1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for loopback primary address and its next-hops.
    fib_ipv6_loopback_connected_route_primary = rib_ipv6_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for old loopback primary address and its next-hops.
    rib_ipv4_old_loopback_connected_route_primary = dict()
    rib_ipv4_old_loopback_connected_route_primary['Route'] = '4.4.4.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for old loopback primary address and its next-hops.
    fib_ipv4_old_loopback_connected_route_primary = rib_ipv4_old_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for old loopback primary address and its next-hops.
    rib_ipv6_old_loopback_connected_route_primary = dict()
    rib_ipv6_old_loopback_connected_route_primary['Route'] = '4:4::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for old loopback primary address and its next-hops.
    fib_ipv6_old_loopback_connected_route_primary = rib_ipv6_old_loopback_connected_route_primary

    # Add more secondary IPv4 and IPv6 addresses on the L3 LAG interface
    sw1("configure terminal")
    sw1("interface lag 100")
    sw1("ip address 77.77.77.77/24 secondary")
    sw1("ipv6 address 77:77::77/64 secondary")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    rib_ipv4_lag_connected_route_primary = dict()
    rib_ipv4_lag_connected_route_primary['Route'] = '5.5.5.0/24'
    rib_ipv4_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_primary['lag100'] = dict()
    rib_ipv4_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    fib_ipv4_lag_connected_route_primary = rib_ipv4_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for first LAG secondary address and its next-hops.
    rib_ipv4_first_lag_connected_route_secondary = dict()
    rib_ipv4_first_lag_connected_route_secondary['Route'] = '55.55.55.0/24'
    rib_ipv4_first_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_first_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv4_first_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv4_first_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv4_first_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for first LAG secondary address and its next-hops.
    fib_ipv4_first_lag_connected_route_secondary = rib_ipv4_first_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for second LAG secondary address and its next-hops.
    rib_ipv4_second_lag_connected_route_secondary = dict()
    rib_ipv4_second_lag_connected_route_secondary['Route'] = '77.77.77.0/24'
    rib_ipv4_second_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_second_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv4_second_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv4_second_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv4_second_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for second LAG secondary address and its next-hops.
    fib_ipv4_second_lag_connected_route_secondary = rib_ipv4_second_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    rib_ipv6_lag_connected_route_primary = dict()
    rib_ipv6_lag_connected_route_primary['Route'] = '5:5::/64'
    rib_ipv6_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_primary['lag100'] = dict()
    rib_ipv6_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    fib_ipv6_lag_connected_route_primary = rib_ipv6_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for first LAG secondary address and its next-hops.
    rib_ipv6_first_lag_connected_route_secondary = dict()
    rib_ipv6_first_lag_connected_route_secondary['Route'] = '55:55::/64'
    rib_ipv6_first_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_first_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv6_first_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv6_first_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv6_first_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for first LAG secndary address and its next-hops.
    fib_ipv6_first_lag_connected_route_secondary = rib_ipv6_first_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for second LAG secondary address and its next-hops.
    rib_ipv6_second_lag_connected_route_secondary = dict()
    rib_ipv6_second_lag_connected_route_secondary['Route'] = '77:77::/64'
    rib_ipv6_second_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_second_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv6_second_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv6_second_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv6_second_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for second LAG secndary address and its next-hops.
    fib_ipv6_second_lag_connected_route_secondary = rib_ipv6_second_lag_connected_route_secondary

    step("Starting the ops-zebra process on switch 1")

    # Start ops-zebra process on sw1
    sw1(zebra_start_command_string, shell='bash')

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4/IPv6 connected routes on switch 1")

    # Verify IPv4 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_primary)
    aux_route = rib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_layer3_connected_route_primary)

    # Verify IPv4 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_secondary)
    aux_route = rib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_layer3_connected_route_secondary)

    # Verify IPv6 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_primary)
    aux_route = rib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_layer3_connected_route_primary)

    # Verify IPv6 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_secondary)
    aux_route = rib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_layer3_connected_route_secondary)

    # Verify IPv4 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_primary)
    aux_route = rib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_vlan_connected_route_primary)

    # Verify IPv4 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_secondary)
    aux_route = rib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_vlan_connected_route_secondary)

    # Verify IPv6 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_primary)
    aux_route = rib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_vlan_connected_route_primary)

    # Verify IPv6 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_secondary)
    aux_route = rib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_vlan_connected_route_secondary)

    # Verify IPv4 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_subinterface_connected_route_primary)
    aux_route = rib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_subinterface_connected_route_primary)

    # Verify IPv6 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_subinterface_connected_route_primary)
    aux_route = rib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_subinterface_connected_route_primary)

    # Verify IPv4 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_loopback_connected_route_primary)
    aux_route = rib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_loopback_connected_route_primary)

    # Verify IPv6 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_loopback_connected_route_primary)
    aux_route = rib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_loopback_connected_route_primary)

    # Verify IPv4 route for old loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_old_loopback_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_old_loopback_connected_route_primary)
    aux_route = rib_ipv4_old_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_old_loopback_connected_route_primary)

    # Verify IPv6 route for old loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_old_loopback_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_old_loopback_connected_route_primary)
    aux_route = rib_ipv6_old_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_old_loopback_connected_route_primary)

    # Verify IPv4 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_primary)
    aux_route = rib_ipv4_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_lag_connected_route_primary)

    # Verify IPv4 route for first LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_first_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_first_lag_connected_route_secondary)
    aux_route = rib_ipv4_first_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_first_lag_connected_route_secondary)

    # Verify IPv4 route for second LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_second_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_second_lag_connected_route_secondary)
    aux_route = rib_ipv4_second_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_second_lag_connected_route_secondary)

    # Verify IPv6 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_primary)
    aux_route = rib_ipv6_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_lag_connected_route_primary)

    # Verify IPv6 route for first LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_first_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_first_lag_connected_route_secondary)
    aux_route = rib_ipv6_first_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_first_lag_connected_route_secondary)

    # Verify IPv6 route for second LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_second_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_second_lag_connected_route_secondary)
    aux_route = rib_ipv6_second_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_second_lag_connected_route_secondary)


# This test changes some L3 interface configuration after zebra has come up after
# restart. We test the connected routes using the output of
# "show ip/ipv6 route/show rib".
def change_layer3_interface_config_after_zebra_restart(sw1, sw2, step):

    # Change configuration for Layer-3 interface by bringing up the interface
    sw1("configure terminal")
    sw1("interface 1")
    sw1("no shutdown")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    rib_ipv4_layer3_connected_route_primary = dict()
    rib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'
    rib_ipv4_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_primary['1'] = dict()
    rib_ipv4_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    fib_ipv4_layer3_connected_route_primary = rib_ipv4_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 secondary address and its next-hops.
    rib_ipv4_layer3_connected_route_secondary = dict()
    rib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'
    rib_ipv4_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_layer3_connected_route_secondary['1'] = dict()
    rib_ipv4_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv4_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 secndary  address and its next-hops.
    fib_ipv4_layer3_connected_route_secondary = rib_ipv4_layer3_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    rib_ipv6_layer3_connected_route_primary = dict()
    rib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'
    rib_ipv6_layer3_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_primary['1'] = dict()
    rib_ipv6_layer3_connected_route_primary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_primary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    fib_ipv6_layer3_connected_route_primary = rib_ipv6_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 secondary address and its next-hops.
    rib_ipv6_layer3_connected_route_secondary = dict()
    rib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'
    rib_ipv6_layer3_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_layer3_connected_route_secondary['1'] = dict()
    rib_ipv6_layer3_connected_route_secondary['1']['Distance'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['Metric'] = '0'
    rib_ipv6_layer3_connected_route_secondary['1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 secondary  address and its next-hops.
    fib_ipv6_layer3_connected_route_secondary = rib_ipv6_layer3_connected_route_secondary

    # Reconfigure the IPv4 and IPv6 addresses on the Vlan interface
    sw1("configure terminal")
    sw1("interface vlan 100")
    sw1("ip address 2.2.2.2/24")
    sw1("ipv6 address 2:2::2/64")
    sw1("ip address 22.22.22.22/24 secondary")
    sw1("ipv6 address 22:22::22/64 secondary")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    rib_ipv4_vlan_connected_route_primary = dict()
    rib_ipv4_vlan_connected_route_primary['Route'] = '2.2.2.0/24'
    rib_ipv4_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    fib_ipv4_vlan_connected_route_primary = rib_ipv4_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan secondary address and its next-hops.
    rib_ipv4_vlan_connected_route_secondary = dict()
    rib_ipv4_vlan_connected_route_secondary['Route'] = '22.22.22.0/24'
    rib_ipv4_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv4_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan secondary  address and its next-hops.
    fib_ipv4_vlan_connected_route_secondary = rib_ipv4_vlan_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    rib_ipv6_vlan_connected_route_primary = dict()
    rib_ipv6_vlan_connected_route_primary['Route'] = '2:2::/64'
    rib_ipv6_vlan_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_primary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_primary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_primary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    fib_ipv6_vlan_connected_route_primary = rib_ipv6_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan secondary address and its next-hops.
    rib_ipv6_vlan_connected_route_secondary = dict()
    rib_ipv6_vlan_connected_route_secondary['Route'] = '22:22::/64'
    rib_ipv6_vlan_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_vlan_connected_route_secondary['vlan100'] = dict()
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Distance'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['Metric'] = '0'
    rib_ipv6_vlan_connected_route_secondary['vlan100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan secondary  address and its next-hops.
    fib_ipv6_vlan_connected_route_secondary = rib_ipv6_vlan_connected_route_secondary

    # Do not change the L3 configure on the L3 sub-interface

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    rib_ipv4_subinterface_connected_route_primary = dict()
    rib_ipv4_subinterface_connected_route_primary['Route'] = '3.3.3.0/24'
    rib_ipv4_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv4_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv4_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    fib_ipv4_subinterface_connected_route_primary = rib_ipv4_subinterface_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    rib_ipv6_subinterface_connected_route_primary = dict()
    rib_ipv6_subinterface_connected_route_primary['Route'] = '3:3::/64'
    rib_ipv6_subinterface_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_subinterface_connected_route_primary['3.1'] = dict()
    rib_ipv6_subinterface_connected_route_primary['3.1']['Distance'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['Metric'] = '0'
    rib_ipv6_subinterface_connected_route_primary['3.1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_subinterface_connected_route_primary = rib_ipv6_subinterface_connected_route_primary

    # Change back the IPv4 and IPv6 addresses on the loopback interface
    sw1("configure terminal")
    sw1("interface loopback 1")
    sw1("ip address 4.4.4.6/24")
    sw1("ipv6 address 4:4::4/64")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    rib_ipv4_loopback_connected_route_primary = dict()
    rib_ipv4_loopback_connected_route_primary['Route'] = '4.4.4.0/24'
    rib_ipv4_loopback_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_loopback_connected_route_primary['loopback1'] = dict()
    rib_ipv4_loopback_connected_route_primary['loopback1']['Distance'] = '0'
    rib_ipv4_loopback_connected_route_primary['loopback1']['Metric'] = '0'
    rib_ipv4_loopback_connected_route_primary['loopback1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    fib_ipv4_loopback_connected_route_primary = rib_ipv4_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for loopback primary address and its next-hops.
    rib_ipv6_loopback_connected_route_primary = dict()
    rib_ipv6_loopback_connected_route_primary['Route'] = '4:4::/64'
    rib_ipv6_loopback_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_loopback_connected_route_primary['loopback1'] = dict()
    rib_ipv6_loopback_connected_route_primary['loopback1']['Distance'] = '0'
    rib_ipv6_loopback_connected_route_primary['loopback1']['Metric'] = '0'
    rib_ipv6_loopback_connected_route_primary['loopback1']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for loopback primary address and its next-hops.
    fib_ipv6_loopback_connected_route_primary = rib_ipv6_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for old loopback primary address and its next-hops.
    rib_ipv4_old_loopback_connected_route_primary = dict()
    rib_ipv4_old_loopback_connected_route_primary['Route'] = '6.6.6.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for old loopback primary address and its next-hops.
    fib_ipv4_old_loopback_connected_route_primary = rib_ipv4_old_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for old loopback primary address and its next-hops.
    rib_ipv6_old_loopback_connected_route_primary = dict()
    rib_ipv6_old_loopback_connected_route_primary['Route'] = '6:6::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for old loopback primary address and its next-hops.
    fib_ipv6_old_loopback_connected_route_primary = rib_ipv6_old_loopback_connected_route_primary

    # Delete the second secondary IPv4 and IPv6 addresses on the L3 LAG interface
    sw1("configure terminal")
    sw1("interface lag 100")
    sw1("no ip address 77.77.77.77/24 secondary")
    sw1("no ipv6 address 77:77::77/64 secondary")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    rib_ipv4_lag_connected_route_primary = dict()
    rib_ipv4_lag_connected_route_primary['Route'] = '5.5.5.0/24'
    rib_ipv4_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv4_lag_connected_route_primary['lag100'] = dict()
    rib_ipv4_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv4_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    fib_ipv4_lag_connected_route_primary = rib_ipv4_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for first LAG secondary address and its next-hops.
    rib_ipv4_first_lag_connected_route_secondary = dict()
    rib_ipv4_first_lag_connected_route_secondary['Route'] = '55.55.55.0/24'
    rib_ipv4_first_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv4_first_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv4_first_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv4_first_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv4_first_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for first LAG secondary address and its next-hops.
    fib_ipv4_first_lag_connected_route_secondary = rib_ipv4_first_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for second LAG secondary address and its next-hops.
    rib_ipv4_second_lag_connected_route_secondary = dict()
    rib_ipv4_second_lag_connected_route_secondary['Route'] = '77.77.77.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for second LAG secondary address and its next-hops.
    fib_ipv4_second_lag_connected_route_secondary = rib_ipv4_second_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    rib_ipv6_lag_connected_route_primary = dict()
    rib_ipv6_lag_connected_route_primary['Route'] = '5:5::/64'
    rib_ipv6_lag_connected_route_primary['NumberNexthops'] = '1'
    rib_ipv6_lag_connected_route_primary['lag100'] = dict()
    rib_ipv6_lag_connected_route_primary['lag100']['Distance'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['Metric'] = '0'
    rib_ipv6_lag_connected_route_primary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    fib_ipv6_lag_connected_route_primary = rib_ipv6_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for first LAG secondary address and its next-hops.
    rib_ipv6_first_lag_connected_route_secondary = dict()
    rib_ipv6_first_lag_connected_route_secondary['Route'] = '55:55::/64'
    rib_ipv6_first_lag_connected_route_secondary['NumberNexthops'] = '1'
    rib_ipv6_first_lag_connected_route_secondary['lag100'] = dict()
    rib_ipv6_first_lag_connected_route_secondary['lag100']['Distance'] = '0'
    rib_ipv6_first_lag_connected_route_secondary['lag100']['Metric'] = '0'
    rib_ipv6_first_lag_connected_route_secondary['lag100']['RouteType'] = 'connected'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for first LAG secndary address and its next-hops.
    fib_ipv6_first_lag_connected_route_secondary = rib_ipv6_first_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for second LAG secondary address and its next-hops.
    rib_ipv6_second_lag_connected_route_secondary = dict()
    rib_ipv6_second_lag_connected_route_secondary['Route'] = '77:77::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for second LAG secndary address and its next-hops.
    fib_ipv6_second_lag_connected_route_secondary = rib_ipv6_second_lag_connected_route_secondary

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4/IPv6 connected routes on switch 1")

    # Verify IPv4 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_primary)
    aux_route = rib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_layer3_connected_route_primary)

    # Verify IPv4 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_secondary)
    aux_route = rib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_layer3_connected_route_secondary)

    # Verify IPv6 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_primary)
    aux_route = rib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_layer3_connected_route_primary)

    # Verify IPv6 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_secondary)
    aux_route = rib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_layer3_connected_route_secondary)

    # Verify IPv4 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_primary)
    aux_route = rib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_vlan_connected_route_primary)

    # Verify IPv4 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_secondary)
    aux_route = rib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_vlan_connected_route_secondary)

    # Verify IPv6 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_primary)
    aux_route = rib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_vlan_connected_route_primary)

    # Verify IPv6 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_secondary)
    aux_route = rib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_vlan_connected_route_secondary)

    # Verify IPv4 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_subinterface_connected_route_primary)
    aux_route = rib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_subinterface_connected_route_primary)

    # Verify IPv6 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_subinterface_connected_route_primary)
    aux_route = rib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_subinterface_connected_route_primary)

    # Verify IPv4 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_loopback_connected_route_primary)
    aux_route = rib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_loopback_connected_route_primary)

    # Verify IPv6 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_loopback_connected_route_primary)
    aux_route = rib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_loopback_connected_route_primary)

    # Verify IPv4 route for old loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_old_loopback_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_old_loopback_connected_route_primary)
    aux_route = rib_ipv4_old_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_old_loopback_connected_route_primary)

    # Verify IPv6 route for old loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_old_loopback_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_old_loopback_connected_route_primary)
    aux_route = rib_ipv6_old_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_old_loopback_connected_route_primary)

    # Verify IPv4 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_primary)
    aux_route = rib_ipv4_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_lag_connected_route_primary)

    # Verify IPv4 route for first LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_first_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_first_lag_connected_route_secondary)
    aux_route = rib_ipv4_first_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_first_lag_connected_route_secondary)

    # Verify IPv4 route for second LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_second_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_second_lag_connected_route_secondary)
    aux_route = rib_ipv4_second_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_second_lag_connected_route_secondary)

    # Verify IPv6 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_primary)
    aux_route = rib_ipv6_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_lag_connected_route_primary)

    # Verify IPv6 route for first LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_first_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_first_lag_connected_route_secondary)
    aux_route = rib_ipv6_first_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_first_lag_connected_route_secondary)

    # Verify IPv6 route for second LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_second_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_second_lag_connected_route_secondary)
    aux_route = rib_ipv6_second_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_second_lag_connected_route_secondary)


# This test does "no routing/no interface" triggers in L3 interfaces and check
# if the corresponding connected routes have been cleaned-up from FIB and RIB by
# looking into the output of "show ip/ipv6 route/show rib".
def no_routing_or_delete_layer3_interfaces(sw1, sw2, step):

    # Do "no routing" in layer-3 interface
    sw1("configure terminal")
    sw1("interface 1")
    sw1("no routing")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    rib_ipv4_layer3_connected_route_primary = dict()
    rib_ipv4_layer3_connected_route_primary['Route'] = '1.1.1.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 primary address and its next-hops.
    fib_ipv4_layer3_connected_route_primary = rib_ipv4_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for layer-3 secondary address and its next-hops.
    rib_ipv4_layer3_connected_route_secondary = dict()
    rib_ipv4_layer3_connected_route_secondary['Route'] = '11.11.11.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for layer-3 secndary  address and its next-hops.
    fib_ipv4_layer3_connected_route_secondary = rib_ipv4_layer3_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    rib_ipv6_layer3_connected_route_primary = dict()
    rib_ipv6_layer3_connected_route_primary['Route'] = '1:1::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 primary address and its next-hops.
    fib_ipv6_layer3_connected_route_primary = rib_ipv6_layer3_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for layer-3 secondary address and its next-hops.
    rib_ipv6_layer3_connected_route_secondary = dict()
    rib_ipv6_layer3_connected_route_secondary['Route'] = '11:11::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for layer-3 secondary  address and its next-hops.
    fib_ipv6_layer3_connected_route_secondary = rib_ipv6_layer3_connected_route_secondary

    # Un-configure the vlan interface
    sw1("configure terminal")
    sw1("no interface vlan 100")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    rib_ipv4_vlan_connected_route_primary = dict()
    rib_ipv4_vlan_connected_route_primary['Route'] = '2.2.2.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan primary address and its next-hops.
    fib_ipv4_vlan_connected_route_primary = rib_ipv4_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for vlan secondary address and its next-hops.
    rib_ipv4_vlan_connected_route_secondary = dict()
    rib_ipv4_vlan_connected_route_secondary['Route'] = '22.22.22.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for vlan secondary  address and its next-hops.
    fib_ipv4_vlan_connected_route_secondary = rib_ipv4_vlan_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    rib_ipv6_vlan_connected_route_primary = dict()
    rib_ipv6_vlan_connected_route_primary['Route'] = '2:2::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan primary address and its next-hops.
    fib_ipv6_vlan_connected_route_primary = rib_ipv6_vlan_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for vlan secondary address and its next-hops.
    rib_ipv6_vlan_connected_route_secondary = dict()
    rib_ipv6_vlan_connected_route_secondary['Route'] = '22:22::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for vlan secondary  address and its next-hops.
    fib_ipv6_vlan_connected_route_secondary = rib_ipv6_vlan_connected_route_secondary

    # Do "no routing" in the parent interface for the L3 sub-interface.
    sw1("configure terminal")
    sw1("interface 3")
    sw1("no routing")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    rib_ipv4_subinterface_connected_route_primary = dict()
    rib_ipv4_subinterface_connected_route_primary['Route'] = '3.3.3.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for sub-interface primary address and its next-hops.
    fib_ipv4_subinterface_connected_route_primary = rib_ipv4_subinterface_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    rib_ipv6_subinterface_connected_route_primary = dict()
    rib_ipv6_subinterface_connected_route_primary['Route'] = '3:3::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_subinterface_connected_route_primary = rib_ipv6_subinterface_connected_route_primary

    # Un-configure the loopback interface to remove the loopback interface
    sw1("configure terminal")
    sw1("no interface loopback 1")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    rib_ipv4_loopback_connected_route_primary = dict()
    rib_ipv4_loopback_connected_route_primary['Route'] = '4.4.4.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for loopback primary address and its next-hops.
    fib_ipv4_loopback_connected_route_primary = rib_ipv4_loopback_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for loopback primary address and its next-hops.
    rib_ipv6_loopback_connected_route_primary = dict()
    rib_ipv6_loopback_connected_route_primary['Route'] = '4:4::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for sub-interface primary address and its next-hops.
    fib_ipv6_loopback_connected_route_primary = rib_ipv6_loopback_connected_route_primary

    # Do "no routing" in the L3 lag interface addresses
    sw1("configure terminal")
    sw1("interface lag 100")
    sw1("no routing")
    sw1("exit")

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    rib_ipv4_lag_connected_route_primary = dict()
    rib_ipv4_lag_connected_route_primary['Route'] = '5.5.5.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG primary address and its next-hops.
    fib_ipv4_lag_connected_route_primary = rib_ipv4_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    rib_ipv4_lag_connected_route_secondary = dict()
    rib_ipv4_lag_connected_route_secondary['Route'] = '55.55.55.0/24'

    # Populate the expected RIB ("show ip route") route dictionary for the connected
    # IPv4 route for LAG secondary address and its next-hops.
    fib_ipv4_lag_connected_route_secondary = rib_ipv4_lag_connected_route_secondary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    rib_ipv6_lag_connected_route_primary = dict()
    rib_ipv6_lag_connected_route_primary['Route'] = '5:5::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG primary address and its next-hops.
    fib_ipv6_lag_connected_route_primary = rib_ipv6_lag_connected_route_primary

    # Populate the expected RIB ("show rib") route dictionary for the connected
    # IPv6 route for LAG secondary address and its next-hops.
    rib_ipv6_lag_connected_route_secondary = dict()
    rib_ipv6_lag_connected_route_secondary['Route'] = '55:55::/64'

    # Populate the expected RIB ("show ipv6 route") route dictionary for the connected
    # IPv6 route for LAG secndary address and its next-hops.
    fib_ipv6_lag_connected_route_secondary = rib_ipv6_lag_connected_route_secondary

    sleep(ZEBRA_TEST_SLEEP_TIME)

    step("Verifying the IPv4/IPv6 connected routes on switch 1")

    # Verify IPv4 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_primary)
    aux_route = rib_ipv4_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_layer3_connected_route_primary)

    # Verify IPv4 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_layer3_connected_route_secondary)
    aux_route = rib_ipv4_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_layer3_connected_route_secondary)

    # Verify IPv6 route for layer-3 primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_primary)
    aux_route = rib_ipv6_layer3_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_layer3_connected_route_primary)

    # Verify IPv6 route for layer-3 secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_layer3_connected_route_secondary)
    aux_route = rib_ipv6_layer3_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_layer3_connected_route_secondary)

    # Verify IPv4 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_primary)
    aux_route = rib_ipv4_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_vlan_connected_route_primary)

    # Verify IPv4 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_vlan_connected_route_secondary)
    aux_route = rib_ipv4_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_vlan_connected_route_secondary)

    # Verify IPv6 route for vlan primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_primary)
    aux_route = rib_ipv6_vlan_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_vlan_connected_route_primary)

    # Verify IPv6 route for vlan secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_vlan_connected_route_secondary)
    aux_route = rib_ipv6_vlan_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_vlan_connected_route_secondary)

    # Verify IPv4 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_subinterface_connected_route_primary)
    aux_route = rib_ipv4_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_subinterface_connected_route_primary)

    # Verify IPv6 route for L3-subinterface primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_subinterface_connected_route_primary)
    aux_route = rib_ipv6_subinterface_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_subinterface_connected_route_primary)

    # Verify IPv4 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_loopback_connected_route_primary)
    aux_route = rib_ipv4_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_loopback_connected_route_primary)

    # Verify IPv6 route for loopback primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                         fib_ipv6_loopback_connected_route_primary)
    aux_route = rib_ipv6_loopback_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_loopback_connected_route_primary)

    # Verify IPv4 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_primary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_primary)
    aux_route = rib_ipv4_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv4_lag_connected_route_primary)

    # Verify IPv4 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_ip_route(sw1, aux_route, 'connected',
                         fib_ipv4_lag_connected_route_secondary)
    aux_route = rib_ipv4_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv4_lag_connected_route_secondary)

    # Verify IPv6 route for LAG primary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_primary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_primary)
    aux_route = rib_ipv6_lag_connected_route_primary["Route"]
    verify_show_rib(sw1, aux_route, 'connected', rib_ipv6_lag_connected_route_primary)

    # Verify IPv6 route for LAG secondary address and next-hops in RIB and FIB
    aux_route = fib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_ipv6_route(sw1, aux_route, 'connected',
                           fib_ipv6_lag_connected_route_secondary)
    aux_route = rib_ipv6_lag_connected_route_secondary["Route"]
    verify_show_rib(sw1, aux_route, 'connected',
                    rib_ipv6_lag_connected_route_secondary)


def test_zebra_ct_connected_routes(topology, step):
    sw1 = topology.get("sw1")
    sw2 = topology.get("sw2")

    assert sw1 is not None
    assert sw2 is not None

    # Test case init time sleep
    sleep(ZEBRA_INIT_SLEEP_TIME)

    configure_layer3_interfaces(sw1, sw2, step)
    shutdown_layer3_interfaces(sw1, sw2, step)
    no_shutdown_layer3_interfaces(sw1, sw2, step)
    remove_addresses_from_layer3_interfaces(sw1, sw2, step)
    reconfigure_addresses_on_layer3_interfaces(sw1, sw2, step)
    restart_zebra_with_config_change_for_layer3_interfaces(sw1, sw2, step)
    change_layer3_interface_config_after_zebra_restart(sw1, sw2, step)
    no_routing_or_delete_layer3_interfaces(sw1, sw2, step)
