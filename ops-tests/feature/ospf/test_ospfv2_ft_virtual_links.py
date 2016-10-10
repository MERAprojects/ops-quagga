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
from ospf_configs import wait_for_adjacency, verify_virtual_links
from pytest import fixture
from interface_utils import verify_turn_on_interfaces

TOPOLOGY = """
#
#                 ABR
#                  |
#      1  area 1   | area 0
#   DUT<--------->sw1
#    |  2      1
#    |area 2
#    |  2
#   sw3
#

# Nodes
[type=openswitch name="Dut 1"] dut1
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 3"] sw3

# Links
dut1:2 -- sw3:2
dut1:1 -- sw1:1
"""

# Generic macros used across the test cases
DUT1_INTF1_IPV4_ADDR = "10.10.20.1/24"
DUT1_INTF2_IPV4_ADDR = "10.10.10.1/24"
SW1_INTF1_IPV4_ADDR = "10.10.20.2/24"
SW1_INTF2_IPV4_ADDR = "10.10.30.1/24"
SW3_INTF2_IPV4_ADDR = "10.10.10.2/24"


DUT1_INTF1 = "1"
DUT1_INTF2 = "2"
SW1_INTF1 = "1"
SW1_INTF2 = "2"
SW3_INTF2 = "2"

DUT1_ROUTER_ID = "5.5.5.5"
SW1_ROUTER_ID = "1.1.1.1"
SW3_ROUTER_ID = "3.3.3.3"

OSPF_AREA_1 = "1"
OSPF_AREA_0 = "0"
OSPF_AREA_2 = "2"


@fixture(scope='module')
def configuration(topology, request):

    dut1 = topology.get('dut1')
    sw1 = topology.get('sw1')
    sw3 = topology.get('sw3')

    assert dut1 is not None
    assert sw1 is not None
    assert sw3 is not None

    configure_interface(dut1, DUT1_INTF1, DUT1_INTF1_IPV4_ADDR)
    configure_interface(dut1, DUT1_INTF2, DUT1_INTF2_IPV4_ADDR)
    configure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    configure_interface(sw3, SW3_INTF2, SW3_INTF2_IPV4_ADDR)

    verify_turn_on_interfaces(sw1, [sw1.ports[SW1_INTF1]])
    verify_turn_on_interfaces(sw3, [sw3.ports[SW3_INTF2]])

    # Configuring ospf with network command in dut1, sw1 and sw3
    configure_ospf_router(dut1, DUT1_ROUTER_ID, DUT1_INTF1_IPV4_ADDR,
                          OSPF_AREA_1)
    configure_ospf_router(dut1, DUT1_ROUTER_ID, DUT1_INTF2_IPV4_ADDR,
                          OSPF_AREA_2)
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR,
                          OSPF_AREA_1)
    configure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF2_IPV4_ADDR,
                          OSPF_AREA_0)
    configure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF2_IPV4_ADDR,
                          OSPF_AREA_2)


def clear_config(topology, request):

    dut1 = topology.get('dut1')
    sw1 = topology.get('sw1')
    sw3 = topology.get('sw3')

    assert dut1 is not None
    assert sw1 is not None
    assert sw3 is not None

    unconfigure_interface(dut1, DUT1_INTF1, DUT1_INTF1_IPV4_ADDR)
    unconfigure_interface(dut1, DUT1_INTF2, DUT1_INTF2_IPV4_ADDR)
    unconfigure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    unconfigure_interface(sw1, SW1_INTF2, SW1_INTF2_IPV4_ADDR)
    unconfigure_interface(sw3, SW3_INTF2, SW3_INTF2_IPV4_ADDR)

    # Unconfiguring ospf with network command in dut1, sw1 and sw3
    unconfigure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF2_IPV4_ADDR,
                            OSPF_AREA_0)
    unconfigure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF2_IPV4_ADDR,
                            OSPF_AREA_0)

    request.addfinalizer(clear_config)


# Test case 11.01 : Verify the virtual link between DUT and remote ABR
# Test case 11.04 : Verify deleting virtual links
def test_ospf_virtual_link(topology, configuration, step):
    dut1 = topology.get('dut1')
    sw1 = topology.get('sw1')
    sw3 = topology.get('sw3')

    assert dut1 is not None
    assert sw1 is not None
    assert sw3 is not None

    step('###### Step 1 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw1, DUT1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and DUT1(router-id = 5.5.5.5)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and DUT1(router-id = %s)" % DUT1_ROUTER_ID

    retval = wait_for_adjacency(sw3, DUT1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and DUT1(router-id = 5.5.5.5)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and DUT1(router-id = %s)" % DUT1_ROUTER_ID

    step('######Step 2- Configuring virtual-links between DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link(OSPF_AREA_1, SW1_ROUTER_ID)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link(OSPF_AREA_1, DUT1_ROUTER_ID)

    step('###### Step 4 - Verifying whether VLINK0 entry is updated'
         'in DUT and SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(40)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID

    step('###### TC- 11.01 --- PASSED ######')

    step('######Step 5- Disabling virtual-links between DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_virtual_link(OSPF_AREA_1, SW1_ROUTER_ID)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_virtual_link(OSPF_AREA_1, DUT1_ROUTER_ID)

    step('###### Step 6 - Verifying whether VLINK0 entry is removed '
         'from SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(40)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID
    else:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')

    step('###### TC - 11.04 --- PASSED ######')


# Test case 11.05 : Verify virtual links on a stubby and
# a totally stubby area
def test_ospf_virtual_on_stubby_area(topology, configuration, step):
    dut1 = topology.get('dut1')
    sw1 = topology.get('sw1')
    sw3 = topology.get('sw3')

    assert dut1 is not None
    assert sw1 is not None
    assert sw3 is not None

    step('###### Step 1 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw1, DUT1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and DUT1(router-id = 5.5.5.5)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and DUT1(router-id = %s)" % DUT1_ROUTER_ID

    retval = wait_for_adjacency(sw3, DUT1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and DUT1(router-id = 5.5.5.5)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and DUT1(router-id = %s)" % DUT1_ROUTER_ID

    step('######Step 2- Configuring the stub area on DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_stub(OSPF_AREA_1)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_stub(OSPF_AREA_1)

    step('######Step 3- Configuring virtual-links between DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link(OSPF_AREA_1, SW1_ROUTER_ID)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link(OSPF_AREA_1, DUT1_ROUTER_ID)

    step('###### Step 4 - Verifying that VLINK0 entry is not updated '
         'in  SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(40)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID
    else:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')

    step('###### Step 5- Removing stub area configurations from '
         'DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_stub(OSPF_AREA_1)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_stub(OSPF_AREA_1)

    step('######Step 6- Disabling virtual-links between DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_virtual_link(OSPF_AREA_1, SW1_ROUTER_ID)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_virtual_link(OSPF_AREA_1, DUT1_ROUTER_ID)

    step('######Step 7- Configuring the Totally stubby '
         'area on DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_stub_no_summary(OSPF_AREA_1)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_stub_no_summary(OSPF_AREA_1)

    step('######Step 8- Configuring virtual-links between DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link(OSPF_AREA_1, SW1_ROUTER_ID)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link(OSPF_AREA_1, DUT1_ROUTER_ID)

    step('###### Step 4 - Verifying that VLINK0 entry is not updated '
         'in  SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(40)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID
    else:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')

    step('######Step 10- Removing Totally stubby area configurations from '
         'DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_stub_no_summary(OSPF_AREA_1)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_stub_no_summary(OSPF_AREA_1)

    step('######Step 11- Disabling virtual-links between DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_virtual_link(OSPF_AREA_1, SW1_ROUTER_ID)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_virtual_link(OSPF_AREA_1, DUT1_ROUTER_ID)

    step('###### TC 11.05 -- PASSED ######')


# Test case 11.03 : Verify hello-interval, retransmit-interval, transmit-delay
# and dead-interval for virtual links
def test_ospf_virtual_link_intervals(topology, configuration, step):
    dut1 = topology.get('dut1')
    sw1 = topology.get('sw1')
    sw3 = topology.get('sw3')

    assert dut1 is not None
    assert sw1 is not None
    assert sw3 is not None

    step('###### Step 1 - Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw1, DUT1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and DUT1(router-id = 5.5.5.5)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and DUT1(router-id = %s)" % DUT1_ROUTER_ID

    retval = wait_for_adjacency(sw3, DUT1_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and DUT1(router-id = 5.5.5.5)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and DUT1(router-id = %s)" % DUT1_ROUTER_ID

    step('######Step 2- Configuring virtual-links between DUT and SW1'
         ' along with hello-interval, retransmit-interval, transmit-interval'
         ' and dead-interval ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link(OSPF_AREA_1, SW1_ROUTER_ID)
        ctx.area_virtual_link_hello_interval(OSPF_AREA_1, SW1_ROUTER_ID, '30')
        ctx.area_virtual_link_retransmit_interval(OSPF_AREA_1,
                                                  SW1_ROUTER_ID, '30')
        ctx.area_virtual_link_transmit_delay(OSPF_AREA_1, SW1_ROUTER_ID, '30')
        ctx.area_virtual_link_dead_interval(OSPF_AREA_1, SW1_ROUTER_ID, '30')

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link(OSPF_AREA_1, DUT1_ROUTER_ID)
        ctx.area_virtual_link_hello_interval(OSPF_AREA_1,
                                             DUT1_ROUTER_ID, '30')
        ctx.area_virtual_link_retransmit_interval(OSPF_AREA_1,
                                                  DUT1_ROUTER_ID, '30')
        ctx.area_virtual_link_transmit_delay(OSPF_AREA_1,
                                             DUT1_ROUTER_ID, '30')
        ctx.area_virtual_link_dead_interval(OSPF_AREA_1, DUT1_ROUTER_ID, '30')

    step('###### Step 3 - Verifying whether VLINK0 entry is updated '
         'in SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(40)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID

    step('###### Step 4 - Changing the hello-interval of '
         'virtual-links in sw1 ######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link_hello_interval(OSPF_AREA_1,
                                             DUT1_ROUTER_ID, '40')
    step('###### Step 5 - Verifying whether VLINK0 entry is removed '
         'from SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(45)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID
    else:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')

    step('###### Step 6 - Reverting the hello-interval of '
         'virtual-link in sw1 ######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link_hello_interval(OSPF_AREA_1, DUT1_ROUTER_ID, '30')

    step('###### Step 7 - Verifying whether VLINK0 entry is removed '
         'from SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(45)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID

    step('###### Step 8 - Changing the virtual-links '
         'dead-interval in sw1 ######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link_dead_interval(OSPF_AREA_1,
                                            DUT1_ROUTER_ID, '120')

    step('###### Step 9 - Verifying whether VLINK0 entry is removed '
         'from SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(40)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID
    else:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')

    step('###### Step 10 - Reverting the virtual-links '
         'dead-interval in sw1 ######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_virtual_link_dead_interval(OSPF_AREA_1, DUT1_ROUTER_ID, '30')

    step('###### Step 11 - Verifying whether VLINK0 entry is removed '
         'from SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(40)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID

    step('######Step 12 - Disabling virtual-links between DUT and SW1 ######')
    with dut1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_virtual_link(OSPF_AREA_1, SW1_ROUTER_ID)

    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_virtual_link(OSPF_AREA_1, DUT1_ROUTER_ID)

    step('###### Step 13 - Verifying whether VLINK0 entry is removed '
         'from SW1 neighbor table ######')
    # Waiting time for VLINK0 to get updated
    time.sleep(40)
    cmd = 'show ip ospf neighbor'
    raw_result = sw1(cmd.format(**locals()), shell='vtysh')
    output = verify_virtual_links(raw_result, '5.5.5.5')
    if output is True:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to update VLINK entry of "
        "DUT1(router-id = 5.5.5.5) in SW1 neighbor table" % DUT1_ROUTER_ID
    else:
        step('VLINK0 entry of DUT1(router-id = 5.5.5.5) is found in SW1')
    step('###### TC - 11.03 --- PASSED ######')
