# -*- coding: utf-8 -*-
# (C) Copyright 2016 Hewlett Packard Enterprise Development LP
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
##########################################################################


from time import sleep
from pytest import mark
from interface_utils import verify_turn_on_interfaces


TOPOLOGY = """
# +-------+
# |  ops1 |
# +-------+

# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=openswitch name="Openswitch 2"] ops2

# Links
ops1:if01 -- ops2:if01
"""

'''
switch 1 configuration
----------------------

#  router bgp 1
#  bgp router-id 8.0.0.1
#  network 9.0.0.0/8
#  neighbor 8.0.0.2 remote-as 2
#  neighbor 8.0.0.2 route-map 1 in

#  interface 1
#  no shutdown
#  ip address 8.0.0.1/8
switch 2 configuration
----------------------

# router bgp 2
#  bgp router-id 8.0.0.2
#  network 10.0.0.0/8
#  network 11.0.0.0/8
#  neighbor 8.0.0.1 remote-as 1

interface 1
    no shutdown
    ip address 8.0.0.2/8

'''

ip_addr1 = "8.0.0.1"
ip_addr2 = "8.0.0.2"

default_pl = "8"

sw1_router_id = "8.0.0.1"
sw2_router_id = "8.0.0.2"

as_num1 = "1"
as_num2 = "2"

vtysh_cr = '\r\n'
max_wait_time = 100


def enterconfigshell(dut):
    dut("configure terminal")


def enterroutercontext(dut, as_num):
    enterconfigshell(dut)

    dut("router bgp " + as_num)


def enternoroutercontext(dut, as_num):
    enterconfigshell(dut)

    dut("no router bgp " + as_num)

    exitcontext(dut)


def exitcontext(dut):
    dut("end")


def configure_no_route_map(dut, routemap):
    enterconfigshell(dut)

    cmd = "no route-map " + routemap + " permit 20"
    dut(cmd)
    exitcontext(dut)


def configure_router_id(dut, as_num, router_id):
    enterroutercontext(dut, as_num)

    print("Configuring BGP router ID " + router_id)
    dut("bgp router-id " + router_id)
    exitcontext(dut)


def configure_network(dut, as_num, network):
    enterroutercontext(dut, as_num)

    cmd = "network " + network
    dut(cmd)
    exitcontext(dut)


def configure_neighbor(dut, as_num1, network, as_num2):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " remote-as " + as_num2
    dut(cmd)
    exitcontext(dut)


def configure_neighbor_rmap_out(dut, as_num1, network, as_num2, routemap):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " route-map " + routemap + " out"
    dut(cmd)
    exitcontext(dut)


def configure_neighbor_rmap_in(dut, as_num1, network, as_num2, routemap):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " route-map " + routemap + " in"
    dut(cmd)
    exitcontext(dut)


def configure_route_map_atomic_aggregate(dut, routemap, as_num):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "set atomic-aggregate"
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def configure_route_map_set_aggregator(dut, routemap, as_num):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "set aggregator as " + as_num + " 8.0.0.1"
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def verify_bgp_routes(dut, network, next_hop):
    dump = dut("show ip bgp")
    routes = dump.split("\r\n")
    for route in routes:
        if network in route and next_hop in route:
            return True
    return False


def wait_for_route(dut, network, next_hop, condition=True):
    for i in range(max_wait_time):
        found = verify_bgp_routes(dut, network, next_hop)
        if found == condition:
            if condition:
                result = "configuration successfull"
            else:
                result = "configuration not successfull"
            print(result)
            return found
        sleep(1)
    print("### Condition not met after %s seconds ###\n" %
          max_wait_time)
    return found


def verify_routemap_set_atomic_aggregate(switch1, switch2, step):
    step("\n\n######## Verifying route-map 'set atomic-aggregator'########\n")

    step("Configuring no router bgp on SW1")
    enternoroutercontext(switch1, as_num1)

    step("Configuring route-map on SW1")
    configure_route_map_atomic_aggregate(switch1, "BGP_OUT", as_num1)

    step("Configuring router id on SW1")
    configure_router_id(switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "9.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, as_num1, ip_addr2, as_num2)

    step("configuring neighbor routemap on SW1")
    configure_neighbor_rmap_out(
        switch1,  as_num1, ip_addr2, as_num2, "BGP_OUT")

    exitcontext(switch2)

    wait_for_route(switch2, "10.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "11.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "9.0.0.0", "8.0.0.1")

    dump = switch2("sh ip bgp 9.0.0.0")
    set_atomic_aggregate = False

    lines = dump.split('\n')
    for line in lines:
        if 'atomic-aggregate' in line:
            set_atomic_aggregate = True

    assert set_atomic_aggregate, "Failed to configure 'set atomic-aggregate'"

    step("### 'set atomic-aggregate' running succesfully ###\n")


def verify_routemap_set_aggregator(switch1, switch2, step):
    step("\n\n########## Verifying route-map 'set aggregator as'##########\n")

    step("Configuring no router bgp on SW1")
    enternoroutercontext(switch1, as_num1)

    step("Configuring route-map on SW1")
    configure_route_map_set_aggregator(switch1, "BGP_OUT", as_num1)

    step("Configuring router id on SW1")
    configure_router_id(switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "9.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, as_num1, ip_addr2, as_num2)

    step("configuring neighbor routemap on SW1")
    configure_neighbor_rmap_out(switch1,  as_num1, ip_addr2, as_num2,
                                "BGP_OUT")

    wait_for_route(switch2, "10.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "11.0.0.0", "0.0.0.0")
    wait_for_route(switch2, "9.0.0.0", "8.0.0.1")

    dump = switch2("sh ip bgp 9.0.0.0")
    set_aggregator = False

    lines = dump.split('\n')
    for line in lines:
        if 'aggregated by 1 8.0.0.1' in line:
            set_aggregator = True

    assert set_aggregator, "Failed to configure 'set aggregator as'"

    step("### 'set aggregator as' running succesfully ###\n")


def configure(switch1, switch2, step):
    '''
     - Configures the IP address in SW1, SW2 and SW3
     - Creates router bgp instance on SW1 and SW2
     - Configures the router id
     - Configures the network range
     - Configure redistribute and neighbor
    '''

    '''
    - Enable the link.
    - Set IP for the switches.
    '''

    # Enabling interface 1 SW1.
    with switch1.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW1.
        step("Enabling interface1 on SW1")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW1
        step("Configuring IPv4 address on link 1 SW1")
        ctx.ip_address("%s/%s" % (ip_addr1, default_pl))

    verify_turn_on_interfaces(switch1, [switch1.ports["if01"]])

    with switch2.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW2.
        step("Enabling interface1 on SW2")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW2
        step("Configuring IPv4 address on link 1 SW2")
        ctx.ip_address("%s/%s" % (ip_addr2, default_pl))

    verify_turn_on_interfaces(switch2, [switch2.ports["if01"]])

#    For SW1 and SW2, configure bgp
    step("Configuring router id on SW1")
    configure_router_id(switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "9.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, as_num1, ip_addr2, as_num2)

    step("Configuring router id on SW2")
    configure_router_id(switch2, as_num2, sw2_router_id)

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "10.0.0.0/8")

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "11.0.0.0/8")

    step("Configuring neighbors on SW2")
    configure_neighbor(switch2, as_num2, ip_addr1, as_num1)


@mark.timeout(600)
def test_bgp_ft_routemap_atomic_aggregate(topology, step):
    switch1 = topology.get('ops1')
    switch2 = topology.get('ops2')

    assert switch1 is not None
    assert switch2 is not None
    configure(switch1, switch2, step)
    verify_routemap_set_atomic_aggregate(switch1, switch2, step)
    verify_routemap_set_aggregator(switch1, switch2, step)
