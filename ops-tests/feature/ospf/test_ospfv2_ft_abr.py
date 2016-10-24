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
from ospf_configs import verify_router_type
from pytest import fixture
from interface_utils import verify_turn_on_interfaces

TOPOLOGY = """
#
#                 ABR           ABR
#                  |             |
#        area 100  |    area 0   |     area 200
#   sw1<--------->sw2<--------->sw3<------------->sw4
#    |    1      1     2       2      1          1
#    |area 100
#    |
#   sw5
#

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=openswitch name="Switch 3"] sw3
[type=openswitch name="Switch 4"] sw4
[type=openswitch name="Switch 5"] sw5

# Links
sw1:1 -- sw5:2
sw1:2 -- sw2:1
sw2:2 -- sw3:2
sw3:1 -- sw4:1
"""

# Generic macros used across the test cases
SW1_INTF1_IPV4_ADDR = "10.10.10.1/24"
SW1_INTF2_IPV4_ADDR = "10.10.20.1/24"
SW2_INTF1_IPV4_ADDR = "10.10.20.2/24"
SW2_INTF2_IPV4_ADDR = "10.10.30.1/24"
SW3_INTF1_IPV4_ADDR = "10.10.40.1/24"
SW3_INTF2_IPV4_ADDR = "10.10.30.2/24"
SW4_INTF1_IPV4_ADDR = "10.10.40.2/24"
SW5_INTF2_IPV4_ADDR = "10.10.10.2/24"


SW1_INTF1 = "1"
SW1_INTF2 = "2"
SW2_INTF1 = "1"
SW2_INTF2 = "2"
SW3_INTF1 = "1"
SW3_INTF2 = "2"
SW4_INTF1 = "1"
SW5_INTF2 = "2"

SW1_ROUTER_ID = "1.1.1.1"
SW2_ROUTER_ID = "2.2.2.2"
SW3_ROUTER_ID = "3.3.3.3"
SW4_ROUTER_ID = "4.4.4.4"
SW5_ROUTER_ID = "5.5.5.5"

OSPF_AREA_100 = "100"
OSPF_AREA_0 = "0"
OSPF_AREA_200 = "200"


@fixture(scope='module')
def configuration(topology, request):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    sw4 = topology.get('sw4')
    sw5 = topology.get('sw5')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert sw4 is not None
    assert sw5 is not None

    configure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    configure_interface(sw1, SW1_INTF2, SW1_INTF2_IPV4_ADDR)
    configure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)
    configure_interface(sw2, SW2_INTF2, SW2_INTF2_IPV4_ADDR)
    configure_interface(sw3, SW3_INTF1, SW3_INTF1_IPV4_ADDR)
    configure_interface(sw3, SW3_INTF2, SW3_INTF2_IPV4_ADDR)
    configure_interface(sw4, SW4_INTF1, SW4_INTF1_IPV4_ADDR)
    configure_interface(sw5, SW5_INTF2, SW5_INTF2_IPV4_ADDR)

    ports_sw1 = [sw1.ports[SW1_INTF1], sw1.ports[SW1_INTF2]]
    verify_turn_on_interfaces(sw1, ports_sw1)
    ports_sw2 = [sw2.ports[SW2_INTF1], sw2.ports[SW2_INTF2]]
    verify_turn_on_interfaces(sw2, ports_sw2)
    ports_sw3 = [sw3.ports[SW3_INTF1], sw3.ports[SW3_INTF2]]
    verify_turn_on_interfaces(sw3, ports_sw3)
    ports_sw4 = [sw4.ports[SW4_INTF1]]
    verify_turn_on_interfaces(sw4, ports_sw4)
    ports_sw5 = [sw5.ports[SW5_INTF2]]
    verify_turn_on_interfaces(sw5, ports_sw5)

    # Configuring ospf with network command in sw1, sw2, sw3, sw4 and sw5
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR,
                          OSPF_AREA_100)
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF2_IPV4_ADDR,
                          OSPF_AREA_100)
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR,
                          OSPF_AREA_100)
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF2_IPV4_ADDR,
                          OSPF_AREA_0)
    configure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF1_IPV4_ADDR,
                          OSPF_AREA_200)
    configure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF2_IPV4_ADDR,
                          OSPF_AREA_0)
    configure_ospf_router(sw4, SW4_ROUTER_ID, SW4_INTF1_IPV4_ADDR,
                          OSPF_AREA_200)
    configure_ospf_router(sw5, SW5_ROUTER_ID, SW5_INTF2_IPV4_ADDR,
                          OSPF_AREA_100)


def clear_config(topology, request):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    sw4 = topology.get('sw4')
    sw5 = topology.get('sw5')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert sw4 is not None
    assert sw5 is not None

    unconfigure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    unconfigure_interface(sw1, SW1_INTF2, SW1_INTF2_IPV4_ADDR)
    unconfigure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)
    unconfigure_interface(sw2, SW2_INTF2, SW2_INTF2_IPV4_ADDR)
    unconfigure_interface(sw3, SW3_INTF1, SW3_INTF1_IPV4_ADDR)
    unconfigure_interface(sw3, SW3_INTF2, SW3_INTF2_IPV4_ADDR)
    unconfigure_interface(sw4, SW4_INTF1, SW4_INTF1_IPV4_ADDR)
    unconfigure_interface(sw5, SW5_INTF2, SW5_INTF2_IPV4_ADDR)

    # Configuring ospf with network command in sw1, sw2, sw3, sw4 and sw5
    unconfigure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR,
                            OSPF_AREA_100)
    unconfigure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF2_IPV4_ADDR,
                            OSPF_AREA_100)
    unconfigure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR,
                            OSPF_AREA_100)
    unconfigure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF2_IPV4_ADDR,
                            OSPF_AREA_0)
    unconfigure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF1_IPV4_ADDR,
                            OSPF_AREA_200)
    unconfigure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF2_IPV4_ADDR,
                            OSPF_AREA_0)
    unconfigure_ospf_router(sw4, SW4_ROUTER_ID, SW4_INTF1_IPV4_ADDR,
                            OSPF_AREA_200)
    unconfigure_ospf_router(sw5, SW5_ROUTER_ID, SW5_INTF2_IPV4_ADDR,
                            OSPF_AREA_100)

    request.addfinalizer(clear_config)


# Test case 6.01 : Test case to verify ABR
def test_ospf_abr(topology, configuration, step):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    sw4 = topology.get('sw4')
    sw5 = topology.get('sw5')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert sw4 is not None
    assert sw5 is not None

    step('###### Step 1 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw2, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW2 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW2 and SW1(router-id = %s)" % SW1_ROUTER_ID

    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    retval = wait_for_adjacency(sw5, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW5 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw5(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW5 and SW1(router-id = %s)" % SW1_ROUTER_ID

    step('###### Step 2 - Verify if SW2 and SW3 are acting as  ABR ######')
    retval = verify_router_type(sw2)
    if(retval == 2):
        step('###### Switch2 is ABR ######')
    else:
        cmd = 'show ip ospf neighbor'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, 'Switch2 failed to become ABR'

    retval = verify_router_type(sw3)
    if(retval == 2):
        step('###### Switch3 is ABR ######')
    else:
        cmd = 'show ip ospf'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, 'Switch3 failed to become ABR'

    # Waiting time for routes of sw3 to be updated
    time.sleep(20)
    step(
        '###### Step 3 -Verifying connected routes to sw1 '
        'using show rib command ######'
        )
    retval = verify_route(sw3, '10.10.10.0', '24')
    if retval is True:
        step('###### Connected route 10.10.10.0/24 is found in sw3 ######')
    else:
        sw3('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Connected route 10.10.10.0/24 not found in sw3'

    retval = verify_route(sw4, '10.10.10.0', '24')
    if retval is True:
        step('###### Connected route 10.10.10.0/24 is found in sw4  ######')
    else:
        sw4('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Connected route 10.10.10.0/24 failed '
        'to be removed'

    step('###### Test Case [6.01] PASSED ######')


# Test case 6.02 : Test case to verify learnt routes are removed
# in inter-area, when switch in another area goes down
def test_ospf_routes_abr(topology, configuration, step):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    sw4 = topology.get('sw4')
    sw5 = topology.get('sw5')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert sw4 is not None
    assert sw5 is not None

    step('###### Step 1 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw2, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW2 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW2 and SW1(router-id = %s)" % SW1_ROUTER_ID

    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    retval = wait_for_adjacency(sw5, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW5 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw5(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW5 and SW1(router-id = %s)" % SW1_ROUTER_ID

    step('###### Step 2 - Verify if SW2 and SW3 are acting as ABR ######')
    retval = verify_router_type(sw2)
    if retval == 2:
        step('###### Switch2 is ABR ######')
    else:
        cmd = 'show ip ospf'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, 'Switch2 not acting as ABR'

    retval = verify_router_type(sw3)
    if retval == 2:
        step('###### Switch3 is ABR ######')
    else:
        cmd = 'show ip ospf'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, 'Switch3 not acting as ABR'

    step('###### Step 3 - Disabling ospf process in switch1 ######')
    with sw1.libs.vtysh.Configure() as ctx:
        ctx.no_router_ospf()

    # Waiting time for routes of sw3 to be updated
    time.sleep(40)
    step(
        '###### Step 4 - Verifying whether connected route 10.10.10.0/24 '
        'is removed from sw3 using show rib command ######'
        )
    retval = verify_route(sw3, '10.10.10.0', '24')
    if retval is True:
        sw3('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Failed to remove connected route from 10.10.10.0/24'
    else:
        step(
            '###### Connected route 10.10.10.0/24 is removed '
            'from sw3 after disabling OSPF in sw1 ######'
            )

    retval = verify_route(sw4, '10.10.10.0', '24')
    if retval is True:
        sw4('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Failed to remove connected route 10.10.10.0 from sw4'
    else:
        step(
            '###### Connected route 10.10.10.0/24 is removed '
            'from sw4 after disabling OSPF in switch1 ######'
            )

    # Enabling OSPF in sw1
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR,
                          OSPF_AREA_100)
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF2_IPV4_ADDR,
                          OSPF_AREA_100)
    step('###### Test Case [6.02] PASSED ######')


# Test case 6.04 : Test case to verify ABR distributes summarized routes
def test_ospf_summarized_routes(topology, configuration, step):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    sw4 = topology.get('sw4')
    sw5 = topology.get('sw5')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert sw4 is not None
    assert sw5 is not None

    step('###### Step 1 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw2, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW2 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW2 and SW1(router-id = %s)" % SW1_ROUTER_ID

    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    retval = wait_for_adjacency(sw5, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW5 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw5(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW5 and SW1(router-id = %s)" % SW1_ROUTER_ID

    # TODO:Summarization is not yet supported
    '''
    step('###### Step2 - Verifying the connected routes in sw1 ######')
    retval = verify_route(sw1, '10.10.10.1', '24')
    if retval is True:
        step('###Switch1 has learnt the route--> 10.10.10.1/24 ###')
    else:
        sw1('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Switch1 failed to learn route ---> 10.10.10.1/24'

    retval = verify_route(sw1, '10.10.20.1', '24')
    if retval is True:
        step('###### Switch1 has learnt the route--> 10.10.20.1/24 ######')
    else:
        sw1('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Switch1 failed to learn route ---> 10.10.20.1/24'
    '''

    step('###### Step 3 - Verify if the switches are ABR ######')
    retval = verify_router_type(sw2)
    if retval == 2:
        step('###### SW2 is ABR ######')
    else:
        cmd = 'show ip ospf'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, 'SW2 failed to become ABR'

    retval = verify_router_type(sw3)
    if retval == 2:
        step('###### SW3 is ABR ######')
    else:
        cmd = 'show ip ospf'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, 'SW3 failed to become ABR'

    # TODO:Summarization is not yet supported
    '''
    step(
        '###### Step4 - Verifying the connected routes to sw1'
        'using show rib command ######'
        )
    retval = verify_route(sw3, '10.10.0.0', '16')
    if retval is True:
        step('###### Connected route from SW3 to SW1 is found ######')
    else:
        sw3('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Connected route from SW3 to SW1 not found'

    retval = verify_route(sw4, '10.10.0.0', '16')
    if retval is True:
        step('###### Connected route from SW4 to  SW1 is removed ######')
    else:
        sw4('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Failed to remove connected route from SW4 to SW1'
    '''
    step('###### Test Case- [6.04] PASSED ######')


# Test case 6.03 : Test case to verify ABR learns and
# distributes networks in between the OSPFv2 areas
def test_ospf_network_betwn_areas(topology, configuration, step):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    sw4 = topology.get('sw4')
    sw5 = topology.get('sw5')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert sw4 is not None
    assert sw5 is not None

    step('###### Step 1 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw2, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW2 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW2 and SW1(router-id = %s)" % SW1_ROUTER_ID

    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    retval = wait_for_adjacency(sw5, SW1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW5 and SW1(router-id = 1.1.1.1)')
    else:
        cmd = 'show ip ospf neighbor'
        sw5(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW5 and SW1(router-id = %s)" % SW1_ROUTER_ID

    step('###### Step 2 - Verify if SW2 and SW3 are acting as ABR ######')
    retval = verify_router_type(sw2)
    if(retval == 2):
        step('###### SW2 is ABR ######')
    else:
        cmd = 'show ip ospf'
        sw2(cmd.format(**locals()), shell='vtysh')
        assert False, 'SW2 failed to become ABR'

    retval = verify_router_type(sw3)
    if(retval == 2):
        step('###### SW3 is ABR ######')
    else:
        cmd = 'show ip ospf'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, 'SW3 failed to become ABR'

    # Waiting time for routes to be updated in sw3
    time.sleep(20)
    step(
        '###### Step 3 - Verifying the connected routes to sw1 '
        'using show rib command ######'
        )
    retval = verify_route(sw3, '10.10.10.0', '24')
    if retval is True:
        step('###### Connected route 10.10.10.0/24 found in sw3 ######')
    else:
        sw3('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Failed to remove connected route 10.10.10.0/24 in sw3'

    retval = verify_route(sw4, '10.10.10.0', '24')
    if retval is True:
        step('###### Connected route 10.10.10.0/24 found in sw4 ######')
    else:
        sw4('show rib'.format(**locals()), shell='vtysh')
        assert False, 'Failed to remove connected route 10.10.10.0/24 in sw4'

    # TODO:
    # Verifying using "show ip ospf database summary"
    # Command is not supported currently
    # step('###### Step 4 - Verifying sw1 learnt routes in sw3 and sw4 #####')

    step('###### Test Case- [6.03]---PASSED ######')
