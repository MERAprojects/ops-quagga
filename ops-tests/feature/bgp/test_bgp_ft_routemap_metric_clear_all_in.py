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

TOPOLOGY = """
# +-------+         +-------+         +-------+
# |  ops1 <1:-----:1>  ops2 <2:-----:1>  ops3 |
# +-------+         +-------+         +-------+

# Nodes
[type=openswitch name="OpenSwitch 1"] ops1
[type=openswitch name="Openswitch 2"] ops2
[type=openswitch name="Openswitch 3"] ops3

# Links
ops1:if01 -- ops2:if01
ops2:if02 -- ops3:if01
"""

'''

switch 1 configuration
----------------------

#  router bgp 1
#  bgp router-id 8.0.0.1
#  network 11.0.0.0/8
#  neighbor 8.0.0.2 remote-as 2
#  neighbor 8.0.0.2 route-map 1 in

#  interface 1
#  no shutdown
#  ip address 8.0.0.1/8
switch 2 configuration
----------------------

# router bgp 2
#  bgp router-id 8.0.0.2
#  network 15.0.0.0/8
#  neighbor 8.0.0.1 remote-as 1
#  neighbor 40.0.0.2 remote-as 3

interface 1
    no shutdown
    ip address 8.0.0.2/8
interface 2
    no shutdown
    ip address 40.0.0.1/8
switch 3 configuration
----------------------

# router bgp 3
#  bgp router-id 8.0.0.3
#  network 12.0.0.0/8
#  neighbor 40.0.0.1 remote-as 2

interface 1
    no shutdown
    ip address 40.0.0.2/8

'''

ip_addr1 = "8.0.0.1"
ip_addr2_1 = "8.0.0.2"
ip_addr2_2 = "40.0.0.1"
ip_addr3 = "40.0.0.2"
default_pl = "8"

sw1_router_id = "8.0.0.1"
sw2_router_id = "8.0.0.2"
sw3_router_id = "8.0.0.3"


network_sw1 = "11.0.0.0/8"
network_sw2 = "15.0.0.0/8"
network_sw3 = "12.0.0.0/8"

as_num1 = "1"
as_num2 = "2"
as_num3 = "3"

vtysh_cr = '\r\n'
max_wait_time = 100


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


def enterconfigshell(dut):
    dut("configure terminal")


# If the context is not present already then it will be created
def enterroutercontext(dut, as_num):
    enterconfigshell(dut)

    dut("router bgp " + as_num)


def clear_soft_in_all(dut):
    dut("clear bgp * soft in")


def enternoroutercontext(dut, as_num):
    enterconfigshell(dut)

    dut("no router bgp " + as_num)

    exitcontext(dut)


def exitcontext(dut):
    dut("end")


def configure_route_map_set_metric(dut, routemap, as_num, metric):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "set metric " + metric
    dut(cmd)
    dut(cmd1)
    exitcontext(dut)


def configure_route_map_match_metric(dut, routemap, as_num, metric):
    enterconfigshell(dut)

    cmd = "route-map " + routemap + " permit 20"
    cmd1 = "match metric " + metric
    dut(cmd)
    dut(cmd1)
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


def configure_no_route_map(dut, routemap):
    enterconfigshell(dut)

    cmd = "no route-map " + routemap + " permit 20"
    dut(cmd)
    exitcontext(dut)


def configure_neighbor_rmap_out(dut, as_num1, network, as_num2, routemap):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " route-map " + routemap + " out"
    dut(cmd)
    exitcontext(dut)


def configure_peer_group(dut, as_num1, group):
    enterroutercontext(dut, as_num1)

    dut("neighbor " + group + " peer-group")
    exitcontext(dut)


def configure_peer_group_member(dut, as_num1, peer_ip, group):
    enterroutercontext(dut, as_num1)

    dut("neighbor " + peer_ip + " peer-group " + group)
    exitcontext(dut)


def configure_neighbor_rmap_in(dut, as_num1, network, as_num2, routemap):
    enterroutercontext(dut, as_num1)

    cmd = "neighbor " + network + " route-map " + routemap + " in"
    dut(cmd)
    exitcontext(dut)


def verify_routemap_set_metric_clear_soft_in_all(topology, step):
    step("\n\n########## Verifying route-map set metric test 1"
         " for clear soft in all command##########\n")

    switch1 = topology.get("ops1")
    assert switch1 is not None
    switch2 = topology.get("ops2")
    assert switch2 is not None
    switch3 = topology.get("ops3")
    assert switch3 is not None

    metric = "18"

    step("Configuring route-map on SW2")
    configure_route_map_set_metric(switch2, "BGP_IN", as_num2, metric)

    step("Configuring neighbor route-map on SW2 for peer 1")
    configure_neighbor_rmap_in(switch2, as_num2, ip_addr1, as_num1, "BGP_IN")

    step("Configuring neighbor route-map on SW2 for peer 3")
    configure_neighbor_rmap_in(switch2, as_num2, ip_addr3, as_num3, "BGP_IN")

    clear_soft_in_all(switch2)

    exitcontext(switch1)
    exitcontext(switch2)
    exitcontext(switch3)

    network1 = neighbor_network_1 = network_sw1
    network3 = neighbor_network_3 = network_sw3

    next_hop1 = "8.0.0.1"
    next_hop3 = "40.0.0.2"

    found = wait_for_route(switch2, network1, next_hop1)

    assert found, "Could not find route (%s -> %s) on %s" % \
        (network1, next_hop1, "ops2")

    found = wait_for_route(switch2, network3, next_hop3)

    assert found, "Could not find route (%s -> %s) on %s" % \
        (network3, next_hop3, "ops2")

    metric_str = ' 18 '
    set_metric_flag_1 = False
    set_metric_flag_3 = False
    dump = switch2("sh ip bgp")
    lines = dump.split('\n')
    for line in lines:
        if neighbor_network_1 in line and metric_str in line:
            set_metric_flag_1 = True
        if neighbor_network_3 in line and metric_str in line:
            set_metric_flag_3 = True

    assert set_metric_flag_1, "Failure to verify clear bgp all soft" \
        " in command on peer 2" \
        " for neighbor %s" % ip_addr1
    assert set_metric_flag_3, "Failure to verify clear bgp all soft" \
                              " in command on peer 2" \
                              " for neighbor %s" % ip_addr3
    step("### 'clear bgp all soft in' validated succesfully "
         "on peer 2 for neighbors %s and %s###\n" %
         (ip_addr1, ip_addr3))


def configure(topology, step):
    '''
     - Configures the IP address in SW1, SW2 and SW3
     - Creates router bgp instance on SW1, SW2 and SW3
     - Configures the router id
     - Configures the network range
     - Configure neighbor
    '''

    switch1 = topology.get("ops1")
    assert switch1 is not None
    switch2 = topology.get("ops2")
    assert switch2 is not None
    switch3 = topology.get("ops3")
    assert switch3 is not None

    '''
    - Enable the link.
    - Set IP for the switches.
    '''
    with switch1.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW1.
        step("Enabling interface1 on SW1")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW1
        step("Configuring IPv4 address on link 1 SW1")
        ctx.ip_address("%s/%s" % (ip_addr1, default_pl))

    with switch2.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW2.
        step("Enabling interface1 on SW2")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW2
        step("Configuring IPv4 address on link 1 SW2")
        ctx.ip_address("%s/%s" % (ip_addr2_1, default_pl))

    with switch2.libs.vtysh.ConfigInterface("if02") as ctx:
        # Enabling interface 2 SW2.
        step("Enabling interface2 on SW1")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 2 of SW2
        step("Configuring IPv4 address on link 2 SW2")
        ctx.ip_address("%s/%s" % (ip_addr2_2, default_pl))

    with switch3.libs.vtysh.ConfigInterface("if01") as ctx:
        # Enabling interface 1 SW3.
        step("Enabling interface1 on SW3")
        ctx.no_shutdown()
        # Assigning an IPv4 address on interface 1 of SW3
        step("Configuring IPv4 address on link 1 SW3")
        ctx.ip_address("%s/%s" % (ip_addr3, default_pl))

    # For SW1, SW2 and SW3, configure bgp
    step("Configuring router id on SW1")
    configure_router_id(switch1, as_num1, sw1_router_id)

    step("Configuring networks on SW1")
    configure_network(switch1, as_num1, "11.0.0.0/8")

    step("Configuring neighbors on SW1")
    configure_neighbor(switch1, as_num1, ip_addr2_1, as_num2)

    step("Configuring router id on SW2")
    configure_router_id(switch2, as_num2, sw2_router_id)

    step("Configuring networks on SW2")
    configure_network(switch2, as_num2, "15.0.0.0/8")

    step("Configuring neighbor 1 on SW2")
    configure_neighbor(switch2, as_num2, ip_addr1, as_num1)

    step("Configuring neighbor 3 on SW2")
    configure_neighbor(switch2, as_num2, ip_addr3, as_num3)

    step("Configuring router id on SW3")
    configure_router_id(switch3, as_num3, sw3_router_id)

    step("Configuring networks on SW3")
    configure_network(switch3, as_num3, "12.0.0.0/8")

    step("Configuring neighbor on SW3")
    configure_neighbor(switch3, as_num3, ip_addr2_2, as_num2)


@mark.gate
def test_bgp_ft_routemap_metric_clear_all_in(topology, step):
    configure(topology, step)
    verify_routemap_set_metric_clear_soft_in_all(topology, step)
