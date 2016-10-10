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
from ospf_configs import wait_for_adjacency
from ospf_configs import unconfigure_interface, unconfigure_ospf_router
from pytest import fixture
from interface_utils import verify_turn_on_interfaces


TOPOLOGY = """
# +-------+              +-------+
# |      2|     Area 1   |2      |
# |  sw2  <-------------->  sw3  |
# |       |              |       |
# +-------+              +-------+

# Nodes
[type=openswitch name="Switch 2"] sw2
[type=openswitch name="Switch 3"] sw3

# Links
sw2:2 -- sw3:2
"""

# Generic macros used across the test cases
SW2_INTF2_IPV4_ADDR = "10.10.10.1/24"
SW3_INTF2_IPV4_ADDR = "10.10.10.2/24"

SW2_INTF2 = "2"
SW3_INTF2 = "2"

SW2_ROUTER_ID = "2.2.2.2"
SW3_ROUTER_ID = "3.3.3.3"

OSPF_AREA_1 = "1"

md5_key = "1"
md5_password = "ospf123"
auth_key = "auth123"


@fixture(scope='module')
def configuration(topology, request):
    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw2 is not None
    assert sw3 is not None

    # Configuring ip address for sw2 and sw3
    configure_interface(sw2, SW2_INTF2, SW2_INTF2_IPV4_ADDR)
    configure_interface(sw3, SW3_INTF2, SW3_INTF2_IPV4_ADDR)

    verify_turn_on_interfaces(sw2, [sw2.ports[SW2_INTF2]])
    verify_turn_on_interfaces(sw3, [sw3.ports[SW3_INTF2]])

    # Configuring ospf with network command in sw2 and sw3
    configure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF2_IPV4_ADDR, OSPF_AREA_1)
    configure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF2_IPV4_ADDR, OSPF_AREA_1)


def unconfiguration(topology, request):

    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw2 is not None
    assert sw3 is not None

    # Configuring ip address for sw2 and sw3
    unconfigure_interface(sw2, SW2_INTF2, SW2_INTF2_IPV4_ADDR)
    unconfigure_interface(sw3, SW3_INTF2, SW3_INTF2_IPV4_ADDR)

    # Configuring ospf with network command in sw1, sw2 and sw3
    unconfigure_ospf_router(sw2, SW2_ROUTER_ID, SW2_INTF2_IPV4_ADDR,
                            OSPF_AREA_1)
    unconfigure_ospf_router(sw3, SW3_ROUTER_ID, SW3_INTF2_IPV4_ADDR,
                            OSPF_AREA_1)

    request.addfinalizer(unconfiguration)


# Test case [7.01] : Test case to verify
# md5 authentication in interface context
def test_ospf_md_authentication(topology, configuration, step):

    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw2 is not None
    assert sw3 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 - Configuring MD5 authentication in sw2 ######')
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_authentication_message_digest()
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_message_digest_key_md5(md5_key, md5_password)

    # Waiting for adjacency to be torn
    step('######Step 3 - Verifying whether adjacency is torn between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID, False)
    if retval is True:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to tear adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID
    else:
        step('Adjacency torn successfully between '
             'SW3 and SW2(router-id = 2.2.2.2)')

    step('######Step 4 - Configuring MD5 authentication in sw3 ######')
    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_authentication_message_digest()
        ctx.ip_ospf_message_digest_key_md5(md5_key, md5_password)

    # Waiting for adjacency to form again
    step('######Step 5 - Verifying whether adjacency is restored between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency restored between '
             'SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 6 - Disabling OSPF '
         'authentication in SW2 and SW3 ######')
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_authentication()
        ctx.no_ip_ospf_message_digest_key(md5_key)

    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_authentication()
        ctx.no_ip_ospf_message_digest_key(md5_key)

    step('########### TEST CASE [7.01] PASSED ###########')


# Test case 7.02 : Test case to verify
# text authentication in interface context
def test_ospf_text_authentication(topology, configuration, step):

    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw2 is not None
    assert sw3 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 - Configuring text authentication in sw2 ######')
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_authentication()
        ctx.ip_ospf_authentication_key(auth_key)

    # Waiting for adjacency to be torn
    step('######Step 3 - Verifying whether adjacency is torn between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID, False)
    if retval is True:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to tear adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID
    else:
        step('Adjacency torn successfully between '
             'SW3 and SW2(router-id = 2.2.2.2)')

    step('######Step 4 - Configuring text authentication in sw3 ######')
    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_authentication()
        ctx.ip_ospf_authentication_key(auth_key)

    # Waiting for adjacency to be restored
    step('######Step 5 - Verifying whether adjacency is restored between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed  successfully between '
             'SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 6 - Disabling the OSPF '
         'authentication in SW2 and SW3 ######')
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_authentication()
        ctx.no_ip_ospf_authentication_key()

    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_authentication()
        ctx.no_ip_ospf_authentication_key()

    step('########### TEST CASE [7.02] PASSED ###########')


# Test case [7.03] : Test case to verify MD5
# authentication configured per area
def test_ospf_md_area_authentication(topology, configuration, step):

    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw2 is not None
    assert sw3 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 - Configuring MD5 authentication '
         'per area in sw2 ######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_authentication_message_digest(OSPF_AREA_1)
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_message_digest_key_md5(md5_key, md5_password)

    # Waiting for adjacency to be torn
    step('######Step 3 - Verifying whether adjacency is torn between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID, False)
    if retval is True:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to tear down adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID
    else:
        step('Adjacency torn successfully between '
             'SW3 and SW2(router-id = 2.2.2.2)')

    step('######Step 4 - Configuring MD5 authentication '
         'per area in sw3 ######')
    with sw3.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_authentication_message_digest(OSPF_AREA_1)
    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_message_digest_key_md5(md5_key, md5_password)

    # Waiting for adjacency to be restored
    step('######Step 5 - Verifying whether adjacency is restored between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed successfully between '
             'SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 6 - Disabling the OSPF '
         'authentication in SW2 and SW3 ######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_authentication(OSPF_AREA_1)
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_message_digest_key(md5_key)

    with sw3.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_authentication(OSPF_AREA_1)
    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_message_digest_key(md5_key)

    step('########### TEST CASE [7.03] PASSED ###########')


# Test case 7.04 : Test case to verify text-based
# authentication configured per area
def test_ospf_area_text_authentication(topology, configuration, step):

    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw2 is not None
    assert sw3 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 - Configuring text authentication '
         'per area in sw2 ######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_authentication(OSPF_AREA_1)
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_authentication_key(auth_key)

    # Waiting for adjacency to be torn
    step('######Step 3 - Verifying whether adjacency is torn between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID, False)
    if retval is True:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to tear adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID
    else:
        step('Adjacency torn successfully between '
             'SW3 and SW2(router-id = 2.2.2.2)')

    step('######Step 4 - Configuring text authentication '
         'per area in sw3 ######')
    with sw3.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_authentication(OSPF_AREA_1)
    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_authentication_key(auth_key)

    # Waiting for adjacency to be restored
    step('######Step 5 - Verifying whether adjacency is restored between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed successfully between '
             'SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to restore adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 6 - Disabling the OSPF '
         'authentication in SW2 and SW3 ######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_authentication(OSPF_AREA_1)
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_authentication_key()

    with sw3.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_authentication(OSPF_AREA_1)
    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_authentication_key()

    step('########### TEST CASE [7.04] PASSED ###########')


# Test case [7.05] : Test case to verify text-based
# authenatication configured in interface context and
# MD5 authentication in router ospf context
def test_ospf_md_based_text_authentication(topology, configuration, step):

    sw2 = topology.get('sw2')
    sw3 = topology.get('sw3')

    assert sw2 is not None
    assert sw3 is not None

    step('######Step 1 -  Verifying adjacency between switches ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed between SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 2 - Configuring MD5 authentication '
         'per area in sw2 ######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_authentication_message_digest(OSPF_AREA_1)

    step('######Step 3 - Configuring text-based authentication on sw2######')
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_authentication()
        ctx.ip_ospf_authentication_key(auth_key)

    # Waiting for adjacency to be torn
    step('######Step 4 - Verifying whether adjacency is torn between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID, False)
    if retval is True:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to tear adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID
    else:
        step('Adjacency torn successfully between '
             'SW3 and SW2(router-id = 2.2.2.2)')

    step('######Step 5 - Configuring MD5 authentication '
         'per area in sw3 ######')
    with sw3.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.area_authentication_message_digest(OSPF_AREA_1)

    step('######Step 6 - Configuring text-based authentication on sw3######')
    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_ospf_authentication()
        ctx.ip_ospf_authentication_key(auth_key)

    # Waiting for adjacency to be restored
    step('######Step 7 - Verifying whether adjacency is restored between '
         'sw2 and sw3 ######')
    retval = wait_for_adjacency(sw3, SW2_ROUTER_ID)
    if retval:
        step('Adjacency formed successfully between '
             'SW3 and SW2(router-id = 2.2.2.2)')
    else:
        cmd = 'show ip ospf neighbor'
        sw3(cmd.format(**locals()), shell='vtysh')
        assert False, "Failed to form adjacency between"
        "SW3 and SW2(router-id = %s)" % SW2_ROUTER_ID

    step('######Step 8 - Disabling the OSPF '
         'authentication in SW2 and SW3 ######')
    with sw2.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_authentication(OSPF_AREA_1)
    with sw2.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_authentication()
        ctx.no_ip_ospf_authentication_key()

    with sw3.libs.vtysh.ConfigRouterOspf() as ctx:
        ctx.no_area_authentication(OSPF_AREA_1)
    with sw3.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.no_ip_ospf_authentication()
        ctx.no_ip_ospf_authentication_key()

    step('########### TEST CASE [7.05] PASSED ###########')
