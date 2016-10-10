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
from ospf_configs import unconfigure_interface, unconfigure_ospf_router
from ospf_configs import wait_for_adjacency, verify_route
from pytest import fixture
from interface_utils import verify_turn_on_interfaces

TOPOLOGY = """
#                       sw1(DUT)
#                   1 __|     |_ 2
#                    |          |
#                 1  |          | 1
#                   sw2        sw3
#

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=openswitch name="Switch 3"] sw3

# Links
sw1:1 -- sw2:1
sw1:2 -- sw3:1
"""

# Generic macros used across the test cases
SW1_INTF1_IPV4_ADDR = "10.10.10.1/24"
SW1_INTF2_IPV4_ADDR = "10.10.20.1/24"
SW2_INTF1_IPV4_ADDR = "10.10.10.2/24"
SW3_INTF1_IPV4_ADDR = "10.10.20.2/24"

SW1_INTF1 = "1"
SW1_INTF2 = "2"
SW2_INTF1 = "1"
SW3_INTF1 = "1"

SW1_ROUTER_ID = "1.1.1.1"
SW2_ROUTER_ID = "2.2.2.2"
SW3_ROUTER_ID = "3.3.3.3"

OSPF_AREA_1 = "1"


@fixture(scope='module')
def configuration(topology, request):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None

    # Configuring ip address for sw1, sw2 and sw3
    configure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    configure_interface(sw1, SW1_INTF2, SW1_INTF2_IPV4_ADDR)
    configure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)
    configure_interface(sw3, SW3_INTF1, SW3_INTF1_IPV4_ADDR)

    ports_sw1 = [sw1.ports[SW1_INTF1], sw1.ports[SW1_INTF2]]
    verify_turn_on_interfaces(sw1, ports_sw1)
    verify_turn_on_interfaces(sw2, [sw2.ports[SW2_INTF1]])
    verify_turn_on_interfaces(sw3, [sw3.ports[SW3_INTF1]])

    # Configuring ospf with network command in sw1, sw2 and sw3
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF2_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF1_IPV4_ADDR, OSPF_AREA_1)


def unconfiguration(topology, request):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None

    # Configuring ip address for sw1, sw2 and sw3
    unconfigure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    unconfigure_interface(sw1, SW1_INTF2, SW1_INTF2_IPV4_ADDR)
    unconfigure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)
    unconfigure_interface(sw3, SW3_INTF1, SW3_INTF1_IPV4_ADDR)

    # Configuring OSPF with network command in sw1, sw2 and sw3
    unconfigure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF2_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)

    request.addfinalizer(unconfiguration)


# Test case 10.01 : Test case to verify DUT as a stub router
def test_ospf_stub(topology, configuration, step):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None

    step('###### Step 1 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw2, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW2 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW2 and SW1(router-id = %s)" % SW1_ROUTER_ID

    retval = wait_for_adjacency(sw3, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW1(router-id = %s)" % SW1_ROUTER_ID

    step('###### Step 2 - Configuring sw1(DUT) as Stub router '
         'using max-metric router-lsa command  ######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.max_metric_router_lsa()

    # Waiting time to configure router as stub
    time.sleep(10)
    step('#### Step 3 - Verifying whether not directly connected route is '
         'removed ####')
    retval = verify_route(sw2, '10.10.20.0', '24')
    if retval is True:
        sw2('show rib'.format(**locals()), shell='vtysh')
        assert False, "Failed to remove OSPF route 10.10.20.0"
    else:
        step('###### OSPF route 10.10.20.0 has been removed ######')

    step('###### TC[10.01] PASSED ######')


# Test case 10.02 : Test case to verify DUT as stub router on startup
def test_ospf_on_startup(topology, configuration, step):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None

    step('###### Step 1 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw2, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW2 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW2 and SW1(router-id = %s)" % SW1_ROUTER_ID

    retval = wait_for_adjacency(sw3, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between "
        "SW3 and SW1(router-id = %s)" % SW1_ROUTER_ID

    step('######Step 2 - Configuring sw1(DUT) as stub router '
         'using max-metric router-lsa on-startup ######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.max_metric_router_lsa_on_startup('10')

    step('#### Step 3 - Verifying whether not directly connected route is '
         'removed ####')
    retval = verify_route(sw2, '10.10.20.0', '24')
    if retval is True:
        sw2('show rib'.format(**locals()), shell='vtysh')
        assert False, "Failed to remove OSPF route 10.10.20.0"
    else:
        step('###### OSPF routes 10.10.20.0 has been removed ######')

    step('##### Step 4 - Waiting to verify if stub router '
         'has acts as normal router')
    # Wait to check if the router acts as normal router after startup
    time.sleep(10)
    step('##### Step 5 - Verifying whether not directly connected route is '
         'removed')
    retval = verify_route(sw2, '10.10.20.0', '24')
    if retval is True:
        step('#### Routes has been removed ####')
    else:
        sw2('show rib'.format(**locals()), shell='vtysh')
        assert False, "Failed to remove OSPF route 10.10.20.0."
    step('###### TEST CASE [10.02] PASSED ######')
