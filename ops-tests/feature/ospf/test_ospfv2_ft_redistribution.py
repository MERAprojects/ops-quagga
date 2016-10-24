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

import time
from ospf_configs import configure_interface, configure_ospf_router
from ospf_configs import wait_for_adjacency, verify_route
from ospf_configs import configure_bgp_network
from ospf_configs import unconfigure_ospf_network
from ospf_configs import unconfigure_interface, unconfigure_ospf_router
from pytest import fixture
from pytest import mark
from interface_utils import verify_turn_on_interfaces


TOPOLOGY = """
# +-------+     	 +-------+              +-------+
# |      1|     Area 1 	 |1     2|             2|       |
# |  sw2  <-------------->  sw3  <-------------->  sw3  |
# |       |       	 |       |              |       |
# +-------+              +-------+              +-------+
#     | 2                                         1 |
#     |                                             |
#     |1                                          1 |
# +-------+                                     +-------+
# |  hs1  |                                     |  hs2  |
# |       |                                     |       |
# +-------+                                     +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=openswitch name="Switch 3"] sw3
[type=host name="Host 1"] hs1
[type=host name="Host 2"] hs2

# Links
sw1:1 -- sw2:1
sw2:2 -- sw3:2
sw1:2 -- hs1:1
sw3:1 -- hs2:1
"""


# Generic macros used across the test cases
SW1_INTF1_IPV4_ADDR = "10.10.10.1/24"
SW1_INTF2_IPV4_ADDR = "10.10.40.1/24"
SW2_INTF1_IPV4_ADDR = "10.10.10.2/24"
SW2_INTF2_IPV4_ADDR = "10.10.20.1/24"
SW3_INTF1_IPV4_ADDR = "10.10.30.1/24"
SW3_INTF2_IPV4_ADDR = "10.10.20.2/24"

SW1_INTF1 = "1"
SW1_INTF2 = "2"
SW2_INTF1 = "1"
SW2_INTF2 = "2"
SW3_INTF1 = "1"
SW3_INTF2 = "2"

SW1_ROUTER_ID = "1.1.1.1"
SW2_ROUTER_ID = "2.2.2.2"
SW3_ROUTER_ID = "3.3.3.3"

SW2_NEIGHBOR = "10.10.20.2"
SW3_NEIGHBOR = "10.10.20.1"

ASN_2 = "65001"
ASN_3 = "65002"

OSPF_AREA_1 = "1"


@fixture(scope='module')
def configuration(topology, request):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert hs1 is not None
    assert hs2 is not None

    # Configuring ip address for sw2 and sw3
    configure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    configure_interface(sw1, SW1_INTF2, SW1_INTF2_IPV4_ADDR)
    configure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)
    configure_interface(sw2, SW2_INTF2, SW2_INTF2_IPV4_ADDR)
    configure_interface(sw3, SW3_INTF1, SW3_INTF1_IPV4_ADDR)
    configure_interface(sw3, SW3_INTF2, SW3_INTF2_IPV4_ADDR)

    ports_sw1 = [sw1.ports[SW1_INTF1], sw1.ports[SW1_INTF2]]
    verify_turn_on_interfaces(sw1, ports_sw1)
    ports_sw2 = [sw2.ports[SW2_INTF1], sw2.ports[SW2_INTF2]]
    verify_turn_on_interfaces(sw2, ports_sw2)
    ports_sw3 = [sw3.ports[SW3_INTF1], sw3.ports[SW3_INTF2]]
    verify_turn_on_interfaces(sw3, ports_sw3)

    # Configure IP and bring UP host 1 interfaces
    hs1.libs.ip.interface('1', addr='10.10.40.2/24', up=True)

    # Configure IP and bring UP host 2 interfaces
    hs2.libs.ip.interface('1', addr='10.10.30.2/24', up=True)

    # Configuring ospf with network command in sw2 and sw3
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF2_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF2_IPV4_ADDR, OSPF_AREA_1)


def unconfiguration(topology, request):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert hs1 is not None
    assert hs2 is not None

    # Configuring ip address for sw2 and sw3
    unconfigure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    unconfigure_interface(sw1, SW1_INTF2, SW1_INTF2_IPV4_ADDR)
    unconfigure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)
    unconfigure_interface(sw2, SW2_INTF2, SW2_INTF2_IPV4_ADDR)
    unconfigure_interface(sw3, SW3_INTF1, SW3_INTF1_IPV4_ADDR)
    unconfigure_interface(sw3, SW3_INTF2, SW3_INTF2_IPV4_ADDR)

    # Configuring ospf with network command in sw1, sw2 and sw3
    unconfigure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF2_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)

    request.addfinalizer(unconfiguration)


# Test case [4.01] : Test case to verify
# redistribution of static routes
def test_ospf_redistribute_static_routes(topology, configuration, step):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert hs1 is not None
    assert hs2 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 - Configuring static routes in sw2 ######')
    with sw2.libs.vtysh.Configure() as ctx:
        ctx.ip_route('192.168.1.0/24', '1')
        ctx.ip_route('192.168.2.0/24', '1')
        ctx.ip_route('192.168.3.0/24', '1')

    step('######Step 3 - Redistibuting static routes configued in sw1 ######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.redistribute_static()

    # Waiting for static route to get updated in show rib command
    time.sleep(10)
    step('######step 4 - Verifying the sw2 advertised routes in sw1 ######')
    retval = verify_route(sw1, '192.168.1.0', '24')
    if retval is True:
        step('Static route 192.168.1.0 in SW2 is advertised to SW1')
    else:
        sw1('show rib'.format(**locals()), shell='vtysh')
        assert False, "Static route 192.168.1.0 in SW2 is not"
        " advertised to SW1"

    retval = verify_route(sw1, '192.168.2.0', '24')
    if retval is True:
        step('Static route 192.168.2.0 in SW2 is advertised to SW1')
    else:
        sw1('show rib'.format(**locals()), shell='vtysh')
        assert False, "Static route 192.168.2.0 in SW2 is not"
        " advertised to SW1"

    retval = verify_route(sw1, '192.168.3.0', '24')
    if retval is True:
        step('Static route 192.168.3.0 in SW2 is advertised to SW1')
    else:
        sw1('show rib'.format(**locals()), shell='vtysh')
        assert False, "Static route 192.168.3.0 in SW2 is not"
        " advertised to SW1"

    step('######Step 5 - Disabling static route redistribution '
         'on sw1######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_redistribute_static()

    step('########### TEST CASE [4.01] PASSED ###########')


# Test case 4.02 : Test case to verify
# redistribution of connected routes
def test_ospf_redistribute_connected_routes(topology, configuration, step):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert hs1 is not None
    assert hs2 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 - Redistibuting connected routes in sw1######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.redistribute_connected()

    # Waiting for connected route to get updated in show rib command
    time.sleep(10)
    step('######step 3 - Verifying the sw1 advertised routes in sw2 ######')
    retval = verify_route(sw2, '10.10.40.0', '24')
    if retval is True:
        step('sw1 connected routes successfully advertised to sw2')
    else:
        sw2('show rib'.format(**locals()), shell='vtysh')
        assert False, "sw1 connected routes not advertised to sw2"

    step('###### Step 4 - Disabling redistibution of connected '
         'route in sw1 ######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_redistribute_connected()

    step('########### TEST CASE [4.02] PASSED ###########')


# Test case [4.03] : Test case to verify
# redistribution of bgp routes
def test_ospf_redistribute_bgp_routes(topology, configuration, step):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert hs1 is not None
    assert hs2 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('###### Step 2 - Disabling OSPF process in sw3 ######')
    with sw3.libs.vtysh.Configure() as ctx:
        ctx.no_router_ospf()

    step('###### Step 3 - Disabling OSPF configuration from '
         'sw2 ---> interface 2 ######')
    unconfigure_ospf_network(sw2, SW2_INTF2_IPV4_ADDR, OSPF_AREA_1)

    step('######Step 4 - Redistibuting BGP routes to sw1######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.redistribute_bgp()

    step('######Step 5 - Configuring BGP in sw2 and sw3')
    configure_bgp_network(sw2, ASN_2, SW2_ROUTER_ID,
                          SW2_INTF1_IPV4_ADDR, SW2_NEIGHBOR, ASN_3)

    configure_bgp_network(sw3, ASN_3, SW3_ROUTER_ID,
                          SW3_INTF1_IPV4_ADDR, SW3_NEIGHBOR, ASN_2)

    # Waiting for BGP routes to be updated in show rib command
    time.sleep(20)
    step('###### Verifying the redistributed BGP route '
         'in sw3 from sw1 ######')
    retval = verify_route(sw1, '10.10.30.0', '24')
    if retval is True:
        step('###### Redistributed bgp route present in sw1 ######')
    else:
        sw1('show rib'.format(**locals()), shell='vtysh')
        assert False, 'sw2 Failed to redistribute BGP routes'

    step('###### Step 6 - Disabling BGP process in sw2 and sw3 ######')
    with sw2.libs.vtysh.Configure() as ctx:
        ctx.no_router_bgp(ASN_2)
    with sw3.libs.vtysh.Configure() as ctx:
        ctx.no_router_bgp(ASN_3)

    step('###### Step 7 - Enabling OSPF configurations '
         'in sw2 and sw3 ######')
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF2_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF2_IPV4_ADDR, OSPF_AREA_1)

    step('########### TEST CASE [4.03] PASSED ###########')


# Test case 4.04 : Test case to verify redistribution of default route
def test_ospf_redistribute_default_routes(topology, configuration, step):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert hs1 is not None
    assert hs2 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 - Configuring default routes in sw1 ######')
    with sw1.libs.vtysh.Configure() as ctx:
        ctx.ip_route('0.0.0.0/0', '1')

    step('######Step 3 - Redistibuting default routes in sw1 ######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.default_information_originate_always()

    # Waiting for default route to get updated in show rib command
    time.sleep(10)
    step('######step 4 - Verifying the sw1 default routes in sw2 ######')
    retval = verify_route(sw2, '0.0.0.0', '0')
    if retval is True:
        step('sw2 connected routes advertised to sw1')
    else:
        sw2('show rib'.format(**locals()), shell='vtysh')
        assert False, "sw2 connected routes not advertised to sw1"

    step('########### TEST CASE [4.04] PASSED ###########')
