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

from ospf_configs import configure_interface, configure_ospf_router
from ospf_configs import wait_for_adjacency, wait_for_route_distance
from ospf_configs import unconfigure_interface, unconfigure_ospf_router
from ospf_configs import wait_for_best_route, verify_ip_route
from pytest import fixture
from interface_utils import verify_turn_on_interfaces


TOPOLOGY = """
#      +-------+
#      |       |
#      |  sw1  |
#      |       |
#      +-------+
#          |1
#          |
#          |1
#      +-------+
#      |  sw2  |
#      |       |
#      +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2

# Links
sw1:1 -- sw2:1
"""


# Generic macros used across the test cases
SW1_INTF1_IPV4_ADDR = "10.10.10.1/24"
SW2_INTF1_IPV4_ADDR = "10.10.10.2/24"

OSPF_NETWRK_ADDR = "10.10.10.0/24"

SW1_INTF1 = "1"
SW2_INTF1 = "1"

SW1_ROUTER_ID = "1.1.1.1"
SW2_ROUTER_ID = "2.2.2.2"

OSPF_AREA_1 = "1"


@fixture(scope='module')
def configuration(topology, request):
    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')

    assert sw1 is not None
    assert sw2 is not None

    # Configuring ip address for sw2 and sw3
    configure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    configure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)

    verify_turn_on_interfaces(sw1, sw1.ports[SW1_INTF1])
    verify_turn_on_interfaces(sw2, sw2.ports[SW2_INTF1])

    # Configuring ospf with network command in sw2 and sw3
    configure_ospf_router(sw1, SW1_ROUTER_ID, OSPF_NETWRK_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw2, SW2_ROUTER_ID, OSPF_NETWRK_ADDR, OSPF_AREA_1)


def unconfiguration(topology, request):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')

    assert sw1 is not None
    assert sw2 is not None

    # Configuring ip address for sw2 and sw3
    unconfigure_interface(sw1, SW1_INTF1, SW1_INTF1_IPV4_ADDR)
    unconfigure_interface(sw2, SW2_INTF1, SW2_INTF1_IPV4_ADDR)

    # Configuring ospf with network command in sw1, sw2 and sw3
    unconfigure_ospf_router(sw1, SW1_ROUTER_ID, SW1_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF1_IPV4_ADDR,
                            OSPF_AREA_1)

    request.addfinalizer(unconfiguration)


# Test case [13.01] : Verify best route selection by GNU Zebra
def test_ospf_best_route(topology, configuration, step):

    sw1 = topology.get('sw1')
    sw2 = topology.get('sw2')

    assert sw1 is not None
    assert sw2 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw1, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW1 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW1 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 - Configuring external distance in SW1 ######')
    with sw1.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.distance_ospf_external('80')

    step('######Step 3 - Configuring static routes in SW2 ######')
    with sw2.libs.vtysh.Configure() as ctx:
        ctx.ip_route('192.168.1.0/24', '1')

    step('######Step 4 - Redistibuting static routes configured in SW2 ######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.redistribute_static()

    step('######step 5 - Verifying the static routes from sw2 is advertised in sw1 ######')
    retval = wait_for_route_distance(sw1, '192.168.1.0', '24', '80')
    if retval is True:
        step('Static route 192.168.1.0/24 with distance metrics "80" is'
             ' advertised to SW1')
    else:
        sw1('show rib'.format(**locals()), shell='vtysh')
        assert False, "Static route 192.168.1.0/24 with distance metrics 80"
        " is not advertised to SW1"

    step('######step 6 - Configuring static routes in SW1 ######')
    with sw1.libs.vtysh.Configure() as ctx:
        ctx.ip_route('192.168.1.0/24', '1', '100')

    step('######step 7 - Verifying static route from show running config'
         ' ######')
    retval = verify_ip_route(sw1, '192.168.1.0', '24', '1')
    if retval is True:
        step('Static route 192.168.1.0/24 updated in running configuration')
    else:
        cmd = 'show_running_config'
        sw1(cmd.format(**locals()), shell='vtysh')
        assert False, "Static route 192.168.1.0/24 not found"

    step('######step 8 - Verifying statically configured '
         'local routes in SW1 ######')
    retval = wait_for_route_distance(sw1, '192.168.1.0', '24', '100')
    if retval is True:
        step('Static route 192.168.1.0/24 with distance metrics "100" is'
             ' updated in SW1 RIB table')
    else:
        sw1('show rib'.format(**locals()), shell='vtysh')
        assert False, "Static route 192.168.1.0/24 with distance metrics 100"
        " is not updated in SW1 RIB table"

    step('######step 9 - Verifying the best route in SW1 ######')
    retval = wait_for_best_route(sw1, '192.168.1.0', '80', 'ospf')
    if retval is True:
        step('OSPF route 192.168.1.0/24 in SW1 with distance metrics *80* '
             'is selected as best route')
    else:
        sw1('show ip route'.format(**locals()), shell='vtysh')
        assert False, "OSPF route 192.168.1.0/24 in SW1 with "
        "distance metrics *80* failed to be selected as best route"

    step('########### TEST CASE [13.01] PASSED ###########')
