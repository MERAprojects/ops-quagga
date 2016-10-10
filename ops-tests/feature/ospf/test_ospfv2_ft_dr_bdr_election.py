# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Hewlett Packard Enterprise Development LP
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

from ospf_configs import configure_interface, configure_ospf_router
from ospf_configs import wait_for_adjacency, verify_ospf_priority
from ospf_configs import wait_for_2way_state, get_neighbor_state
from pytest import fixture
from interface_utils import verify_turn_on_interfaces

TOPOLOGY = """
#                         sw4(L2)
#                   1 __|  |_ 2 |__3
#                    |       |     |
#                 1  |       | 1   |1
#                   sw1     sw2    sw3
#

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=openswitch name="Switch 3"] sw3
[type=openswitch name="Switch 4"] sw4

# Links
sw1:1 -- sw4:1
sw2:1 -- sw4:2
sw3:1 -- sw4:3
"""

# Generic macros used accross the test cases
SW1_INTF1_IPV4_ADDR = "10.10.10.1/8"
SW2_INTF1_IPV4_ADDR = "10.10.10.2/8"
SW3_INTF1_IPV4_ADDR = "10.10.10.3/8"

SW1_INTF1 = "1"
SW2_INTF1 = "1"
SW3_INTF1 = "1"

SW1_ROUTER_ID = "2.2.2.2"
SW2_ROUTER_ID = "4.4.4.4"
SW3_ROUTER_ID = "1.1.1.1"

OSPF_AREA_1 = "1"


@fixture(scope='module')
def configuration(topology, request):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    sw4 = topology.get('sw4')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert sw4 is not None

    # Configuring ip address for sw1, sw2 and sw3
    configure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    configure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)
    configure_interface(sw3, SW3_INTF1, SW3_INTF1_IPV4_ADDR)

    verify_turn_on_interfaces(sw1, sw1.ports[SW1_INTF1])
    verify_turn_on_interfaces(sw2, sw2.ports[SW2_INTF1])
    verify_turn_on_interfaces(sw3, sw3.ports[SW3_INTF1])

    # Configuring ospf with network command in sw1, sw2 and sw3
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF1_IPV4_ADDR, OSPF_AREA_1)


# Test case [3.01] : Test case to verify that the DR and BDR is selected
def test_ospfv2_ft_election_dr_bdr(topology, configuration, step):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')
    sw4 = topology.get('sw4')

    assert sw1 is not None
    assert sw2 is not None
    assert sw3 is not None
    assert sw4 is not None

    step('###### Step 1 - configuring sw4 as L2 switch ######')
    with sw4.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.no_routing()
        ctx.no_shutdown()

    with sw4.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_routing()
        ctx.no_shutdown()

    with sw4.libs.vtysh.ConfigInterface('3') as ctx:
        ctx.no_routing()
        ctx.no_shutdown()

    step('###### Step 2 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 4.4.4.4)')
    else:
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 4.4.4.4)')
    else:
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('###### Step 3 - Verifying states of switches ######')
    dr_present = False
    bdr_present = False
    dr_other_present = False

    retval = wait_for_2way_state(sw2, SW1_ROUTER_ID)
    if retval:
        state = get_neighbor_state(sw2, SW1_ROUTER_ID)
        if (state == "Backup"):
            step('Switch1 in DRBackup state')
            bdr_present = True
        elif (state == "DR"):
            step('Switch1 in DR state')
            dr_present = True
        elif (state == "DROther"):
            step('Switch1 in DROther state')
            dr_other_present = True
        else:
            step('Switch1 is not in correct state')
            assert False, "Switch1 is not in correct state"
    else:
        assert False, "SW1 is not in correct state"

    retval = wait_for_2way_state(sw3, SW2_ROUTER_ID)
    if retval:
        state = get_neighbor_state(sw3, SW2_ROUTER_ID)
        if (state == "Backup"):
            step('Switch2 in DRBackup state')
            bdr_present = True
        elif (state == "DR"):
            step('Switch2 in DR state')
            dr_present = True
        elif (state == "DROther"):
            step('Switch2 in DROther state')
            dr_other_present = True
        else:
            step('Switch2 is not in correct state')
            assert False, "Switch1 is not in correct state"
    else:
        assert False, "SW2 is not in correct state"

    retval = wait_for_2way_state(sw1, SW3_ROUTER_ID)
    if retval:
        state = get_neighbor_state(sw1, SW3_ROUTER_ID)
        if (state == "Backup"):
            step('Switch3 in DRBackup state')
            bdr_present = True
        elif (state == "DR"):
            step('Switch3 in DR state')
            dr_present = True
        elif (state == "DROther"):
            step('Switch3 in DROther state')
            dr_other_present = True
        else:
            step('Switch3 is not in correct state')
            assert False, "Switch3 is not in correct state"
    else:
        assert False, "SW3 is not in correct state"

    if (dr_present is False) or (bdr_present is False) or \
       (dr_other_present is False):
        assert False, "DR/BDR election failed"

    step('###### TC- 3.01  PASSED ######')

    # Test case [3.03] : Test case to verify that the BDR is
    # selected as DR when priority values are changed
    step('###### Step 4 - Changing ospf priority of sw1, sw2, sw3 to 0, 10'
         ' and 20 respectively ######')

    with sw1.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.ip_ospf_priority('0')

    with sw2.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.ip_ospf_priority('10')

    with sw3.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.ip_ospf_priority('20')

    step('Step 5 - Verifying the priorities configured '
         'in sw1, sw2 and sw3')
    retval = verify_ospf_priority(sw1, '0')
    if retval is True:
        step('###### Priority value successfully updated '
             ' in OSPF interface of SW1')
    else:
        assert False, "Failed to update priority in SW1"

    retval = verify_ospf_priority(sw2, '10')
    if retval is True:
        step('###### Priority value successfully updated '
             ' in OSPF interface of SW2')
    else:
        assert False, "Failed to update priority in SW2"

    retval = verify_ospf_priority(sw3, '20')
    if retval is True:
        step('###### Priority value successfully updated '
             ' in OSPF interface of SW3')
    else:
        assert False, "Failed to update priority in SW3"
    step('###### TC- 3.03  PASSED ######')
