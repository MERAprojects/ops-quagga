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
from ospf_configs import wait_for_adjacency
from ospf_configs import unconfigure_interface, unconfigure_ospf_router
from pytest import fixture
from interface_utils import verify_turn_on_interfaces

TOPOLOGY = """
# +-------+              +-------+              +------+
# |       |              |       |              |      |
# |  sw1  <-------------->  sw2  <--------------> sw3  |
# |       |              |       |              |      |
# +-------+              +-------+              +------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=openswitch name="Switch 3"] sw3

# Links
sw1:1 -- sw2:1
sw2:2 -- sw3:1
"""

# Generic macros used across the test cases
SW1_INTF1_IPV4_ADDR = "10.0.0.1/24"
SW2_INTF1_IPV4_ADDR = "10.0.0.2/24"
SW2_INTF2_IPV4_ADDR = "10.0.1.1/24"
SW3_INTF1_IPV4_ADDR = "10.0.1.2/24"

SW1_INTF1 = "1"
SW2_INTF1 = "1"
SW2_INTF2 = "2"
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
    configure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)
    configure_interface(sw2, SW2_INTF2, SW2_INTF2_IPV4_ADDR)
    configure_interface(sw3, SW3_INTF1, SW3_INTF1_IPV4_ADDR)

    verify_turn_on_interfaces(sw1, [sw1.ports[SW1_INTF1]])
    ports_sw2 = [sw2.ports[SW2_INTF1], sw2.ports[SW2_INTF2]]
    verify_turn_on_interfaces(sw2, ports_sw2)
    verify_turn_on_interfaces(sw3, [sw3.ports[SW3_INTF1]])

    # Configuring ospf with network command in sw1, sw2 and sw3
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF2_IPV4_ADDR, OSPF_AREA_1)
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
    unconfigure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)
    unconfigure_interface(sw2, SW2_INTF2, SW2_INTF2_IPV4_ADDR)
    unconfigure_interface(sw3, SW3_INTF1, SW3_INTF1_IPV4_ADDR)

    # Configuring OSPF with network command in sw1, sw2 and sw3
    unconfigure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF2_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)

    request.addfinalizer(unconfiguration)


# Test case [2.03] : Test case to verify that adjacency
# is torn when dead timer is changed
def test_ospf_dead_timer(topology, configuration, step):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 -  Changing the dead-timer interval in sw2  ######')
    with sw2.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.ip_ospf_dead_interval('50')

    # Waiting for dead timer + 5(buffer) to expire
    # so that neighbor entry can be removed.
    time.sleep(55)

    step('######Step 3 - Verifying adjacency after changing dead timer ######')
    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID, False)
    if retval is True:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "adjacency still exist  between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID
    else:
        step('Adjacency torn between SW1 and SW2(router-id = 2.2.2.2)')

    step('######Step 4 - Changing the dead-timers to original value ######')
    with sw2.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.ip_ospf_dead_interval('40')

    step('######Step 5 - Verifying adjacency by reverting hello timer ######')
    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('########### TEST CASE [2.03] PASSED ###########')


# Test case 2.04 : Test case to verify that adjacency
# is torn when hello timer is changed
def test_ospf_hello_timer(topology, configuration, step):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None

    step('######Step 2 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 3 -  Changing the hello-timer interval in sw2  ######')
    with sw2.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.ip_ospf_hello_interval('30')

    # Waiting for dead timer + 15(buffer) to expire
    # so that neighbor entry can be removed.
    time.sleep(55)

    step('######Step 4 - Verifying adjacency after changing hello-timer #####')
    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID, False)
    if retval is True:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "adjacency still exist  between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID
    else:
        step('Adjacency torn between SW1 and SW2(router-id = 2.2.2.2)')

    step('######Step 5 - Changing the hello-timers to original value ######')
    with sw2.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.ip_ospf_hello_interval('10')

    step('######Step 6 - Verifying adjacency by reverting hello timer ######')
    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('########### TEST CASE [2.04] PASSED ###########')
