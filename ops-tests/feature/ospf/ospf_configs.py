# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
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

"""
 This is generic functions related to OSPF module.
"""


import time
import re


# This function will return hello timer from
# show ip ospf interface command
def get_hello_timer(switch_id):
    output = switch_id.libs.vtysh.show_ip_ospf_interface()
    if output:
        if 'hello_timer' in output.keys():
            hello_interval = int(output['hello_timer'])
        else:
            hello_interval = 0
    else:
        hello_interval = 0

    return hello_interval


# Function to verify ospf neighbor priority
def verify_ospf_priority(switch_id, priority):
    output = switch_id.libs.vtysh.show_ip_ospf_interface()
    if output:
        priority_value = output['priority']
        if priority_value == priority:
            return True
    return False


# function to get neighbor state DR/BDR/DROTHER
def get_neighbor_state(switch_id, neighbor_id):
    output = switch_id.libs.vtysh.show_ip_ospf_neighbor()
    if output:
        if neighbor_id in output.keys():
            temp = output[neighbor_id]['state']
            str1 = temp.split("/")
            state = str1[1]
            return state
    else:
        return "none"


# This function will return router-id from
# show ip ospf interface command
def get_router_id(switch_id):
    output = switch_id.libs.vtysh.show_ip_ospf_interface()
    if output:
        if 'router_id' in output.keys():
            return int(output['router_id'])
        else:
            return "none"
    else:
        return "none"


# Function to configure ip address into the interface
def configure_interface(switch_id, interface_id, ip_address):
    with switch_id.libs.vtysh.ConfigInterface(interface_id) as ctx:
        ctx.ip_address(ip_address)
        ctx.no_shutdown()


# Function to enable no routing on interface
def enable_no_routing(switch_id, interface_id):
    with switch_id.libs.vtysh.ConfigInterface(interface_id) as ctx:
        ctx.no_shutdown()
        ctx.no_routing()


# Configuring ospf with network command
def configure_ospf_router(switch_id, router_id, network, area):
    with switch_id.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.router_id(router_id)
        ctx.network_area(network, area)


# configure ospf priority
def configure_ospf_priority(switch_id, interface_id, priority):
    with switch_id.libs.vtysh.ConfigInterface(interface_id) as ctx:
        ctx.ip_ospf_priority(priority)


# Configuring ospf router-id
def configure_ospf_router_id(switch_id, router_id):
    with switch_id.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.router_id(router_id)


# Configuring ospf with network command
def configure_ospf_network(switch_id, network, area):
    with switch_id.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.network_area(network, area)


# Configuring BGP asn, router-id, network and neighbor command
def configure_bgp_network(switch_id, asn, router_id,
                          network, neighbor, neighbor_asn):
    with switch_id.libs.vtysh.ConfigRouterBgp(asn) as ctx:
        ctx.bgp_router_id(router_id)
        ctx.network(network)
        ctx.neighbor_remote_as(neighbor, neighbor_asn)


# function to get neighbor state
# down/init/2-way/Exstart/Exchange/Loading/Full
def get_neighbor_adja_state(switch_id, neighbor_id):
    output = switch_id.libs.vtysh.show_ip_ospf_neighbor()
    if output:
        if neighbor_id in output.keys():
            temp = output[neighbor_id]['state']
            str1 = temp.split("/")
            state = str1[0]
            return state
    else:
        return "none"


# Function used to verify neighbor-id in neighbor table
def verify_ospf_adjacency(switch_id, neighbor_id):
    output = switch_id.libs.vtysh.show_ip_ospf_neighbor()
    if output:
        if neighbor_id in output.keys():
            if (output[neighbor_id]['neighbor_id'] == neighbor_id):
                state = get_neighbor_adja_state(switch_id, neighbor_id)
                if (state == "ExStart" or state == "Exchange" or state ==
                        "Loading" or state == "Full"):
                    return True

    return False


# Function to verify adjacency between two switches
def wait_for_adjacency(switch_id, neighbor_id, condition=True):
    wait_time = get_hello_timer(switch_id) + 70
    for i in range(0, wait_time):
        found = verify_ospf_adjacency(switch_id, neighbor_id)
        if found == condition:
            return found
        else:
            time.sleep(1)

    return found


# Function to verify VLINK0 between switches
def verify_virtual_links(raw_result, neighbor_id):
    neighbor_re = (
        r'(?P<neighbor_id>[^ ]+)\s*(?P<priority>[^ ]+)\s*'
        '(?P<state>[^ ]+)'
        r'\s*(?P<dead_time>[^ ]+)\s*(?P<address>[^ ]+)\s*'
        '(?P<interface>[^ ]+)'
        r'\s*(?P<rxmtl>[^ ]+)\s*(?P<rqstl>[^ ]+)\s*(?P<dbsml>[^ ])'
    )
    result = {}
    pattern_found = False
    for line in raw_result.splitlines():
        if (pattern_found is True):
            re_result = re.search(neighbor_re, line)
            if (re_result):
                partial = re_result.groupdict()
                result[partial['interface']] = partial
        else:
            re_result = re.search('-+\s*-+', line)
            if (re_result):
                pattern_found = True

    if result:
        if 'VLINK0' in result.keys():
            output = result['VLINK0']
            if (output['neighbor_id'] == neighbor_id):
                return True
        else:
            return False


# Function to wait until 2-Way or greater state
def wait_for_2way_state(switch_id, neighbor_id):
    hello_time = get_hello_timer(switch_id)
    wait_time = int(hello_time) + 35
    for i in range(wait_time):
        output = switch_id.libs.vtysh.show_ip_ospf_neighbor()
        if output:
            if neighbor_id in output.keys():
                temp = output[neighbor_id]['state']
                str1 = temp.split("/")
                state = str1[0]
                if (state == "ExStart" or state == "Exchange" or state ==
                        "Loading" or state == "Full"):
                    # waiting here for DR/DBR/DROther election
                    time.sleep(10)
                    return True
                else:
                    time.sleep(1)

    return False


# To verify the router-type from
# show ip ospf command
def verify_router_type(switch_id):
    output = switch_id.libs.vtysh.show_ip_ospf()
    if output:
        area_count = int(output['no_of_area'])
        if (area_count == 2):
            return area_count
        else:
            return 0
    else:
        return 0


# Wait for routes to be updated
def wait_for_routes(switch_id, ip_addr, prefix_addr, condition=True):
    wait_time = 40
    for i in range(0, wait_time):
        found = verify_route(switch_id, ip_addr, prefix_addr)
        if found == condition:
            return found
        else:
            time.sleep(1)

    return found


# Verify the connected routes using
# show rib command
def verify_route(switch_id, ip_addr, prefix_addr):
    result = 0
    output = switch_id.libs.vtysh.show_rib()
    if output:
        list_entries = output['ipv4_entries']
        n = len(list_entries)
        for i in range(0, n):
            partial = output['ipv4_entries'][i]
            if partial['id'] == ip_addr and partial['prefix'] == prefix_addr:
                result = 1
        if(result == 1):
            return True
        else:
            return False


# Wait for routes and distance to be updated
def wait_for_route_distance(switch_id, ip_addr, prefix_addr,
                            cost, condition=True):
    wait_time = 40
    for i in range(0, wait_time):
        found = verify_route_distance(switch_id, ip_addr, prefix_addr, cost)
        if found == condition:
            return found
        else:
            time.sleep(1)

    return found


# Verify the routes with distance metrics using
# show rib command
def verify_route_distance(switch_id, ip_addr, prefix_addr, cost):
    output = switch_id.libs.vtysh.show_rib()
    if output:
        list_entries = output['ipv4_entries']
        n = len(list_entries)
        for i in range(0, n):
            partial = output['ipv4_entries'][i]
            metric = output['ipv4_entries'][i]['next_hops'][0]
            if partial['id'] == ip_addr and partial['prefix'] == prefix_addr:
                if metric['distance'] == cost:
                    return True

    return False


# Function to verify OSPF best path
def wait_for_best_route(switch_id, ip_addr, distance, from_field):
    output = switch_id.libs.vtysh.show_ip_route()
    if output:
        route_length = len(output)
        for i in range(0, route_length):
            if (output[i]['id']) == ip_addr:
                if (output[i]['next_hops'][0]['distance']) == distance \
                    and (output[i]['next_hops'][0]['from']) == from_field:
                    return True
    return False


# Function to verify "ip route" from show running configuration
def verify_ip_route(switch_id, ip_addr, prefix, intf_with_cost):
    output = switch_id.libs.vtysh.show_running_config()
    if output:
        result = output['ip_routes'][ip_addr]
        if result['via'] == intf_with_cost and result['prefix'] == prefix:
            return True
    return False

# OSPF functions to handle unconfiguration commands


# Function to unconfigure ip address into the interface
def unconfigure_interface(switch_id, interface_id, ip_address):
    with switch_id.libs.vtysh.ConfigInterface(interface_id) as ctx:
        ctx.no_ip_address(ip_address)
        ctx.shutdown()


# Unconfiguring BGP process
def unconfigure_bgp_network(switch_id, asn, router_id, network,
                            neighbor, neighbor_asn):
    with switch_id.libs.vtysh.ConfigRouterBgp(asn) as ctx:
        ctx.no_bgp_router_id(router_id)
        ctx.no_network(network)
        ctx.no_neighbor_remote_as(neighbor, neighbor_asn)


# Unconfiguring ospf with network command
def unconfigure_ospf_router(switch_id, router_id, network, area):
    with switch_id.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_router_id()
        ctx.no_network_area(network, area)


# Unconfiguring ospf router-id
def unconfigure_ospf_router_id(switch_id, router_id):
    with switch_id.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_router_id(router_id)


# Unconfiguring ospf with network command
def unconfigure_ospf_network(switch_id, network, area):
    with switch_id.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_network_area(network, area)
