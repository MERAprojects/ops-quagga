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


from time import sleep


def route_exists(switch=None, next_hop=None, bgp_network=None):
    """
    Checks if route exists.

    :param switch: device to check.
    :type enode: topology.platforms.base.BaseNode
    :param str next_hop: IPv4 or IPv6 address to check on route:
     - IPv4 address to check on route:
     ``'192.168.20.20'``.
     - IPv6 address to check on route:
     ``'2001::1'``.
    :param str network: IPv4 or IPv6 address to check on route:
     - IPv4 address to check on route:
     ``'192.168.20.20'``.
     - IPv6 address to check on route:
     ``'2001::1'``.
    """
    assert switch is not None
    assert next_hop is not None
    assert bgp_network is not None
    route_exists = False
    route_max_wait_time = 300
    while route_max_wait_time > 0 and not route_exists:
        output = switch("do show ip bgp")
        lines = output.splitlines()
        for line in lines:
            if bgp_network in line and next_hop in line:
                route_exists = True
                break
        sleep(1)
        route_max_wait_time -= 1
    assert route_exists


def route_not_exists(switch, next_hop, bgp_network):
    """
    Checks if route does not exists.

    :param switch: device to check.
    :type enode: topology.platforms.base.BaseNode
    :param str next_hop: IPv4 or IPv6 address to check is not on route:
     - IPv4 address to check is not on route:
     ``'192.168.20.20'``.
     - IPv6 address to check is not on route:
     ``'2001::1'``.
    :param str network: IPv4 or IPv6 address to check is not on route:
     - IPv4 address to check is not on route:
     ``'192.168.20.20'``.
     - IPv6 address to check is not on route:
     ``'2001::1'``.
    """
    assert switch is not None
    assert next_hop is not None
    assert bgp_network is not None
    route_exists = True
    route_max_wait_time = 300
    while route_max_wait_time > 0 and route_exists:
        output = switch("do show ip bgp")
        lines = output.splitlines()
        for line in lines:
            if bgp_network in line and next_hop in line:
                break
        else:
            route_exists = False
        sleep(1)
        route_max_wait_time -= 1
    assert not route_exists


def wait_for_route(switch, next_hop, bgp_network, exists=True):
    """
    Checks the existance or non-existance of a route in a switch.

    :param switch: device to check.
    :type enode: topology.platforms.base.BaseNode
    :param str next_hop: IPv4 or IPv6 address to check on route:
    - IPv4 address to check on route:
    ``'192.168.20.20'``.
    - IPv6 address to check on route:
    ``'2001::1'``.
    :param str network: IPv4 or IPv6 address to check on route:
    - IPv4 address to check on route:
    ``'192.168.20.20'``.
    - IPv6 address to check on route:
    ``'2001::1'``.
    :param bool exists: True looks for existance and False for
    non-existance of a route.
    """
    assert switch is not None
    assert next_hop is not None
    assert bgp_network is not None
    if exists:
        route_exists(switch, next_hop, bgp_network)
    else:
        route_not_exists(switch, next_hop, bgp_network)


__all__ = ["wait_for_route"]
