# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Hewlett Packard Enterprise Development LP
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

from time import sleep

TOPOLOGY = """
#
#
# +-------+
# +  sw1  +
# +-------+
#
#

# Nodes
[type=openswitch name="Switch 1"] sw1

"""

def test_ospf_ct_verify_router_id(topology, step):
    sw = topology.get('sw1')
    ospf_auto_router_id = "192.168.1.1"
    ospf_man_router_id = "1.1.1.1"
    lo2_addr = "172.16.1.1"
    assert sw is not None

    step('### Test to verify correct OSPF router-id assignment ###')
    step('### 1. Test that router-id is assigned automatically from VRF table ###')
    sw("configure terminal")
    sw("interface loopback 1")
    sw("ip address %s/32" % ospf_auto_router_id)
    sw("exit")
    sw("configure terminal")
    sw("interface loopback 2")
    sw("ip address %s/32" % lo2_addr)
    sw("exit")
    sw("router ospf")
    ospf_cfg = sw("do show ip ospf")
    assert "Router ID:  %s" % ospf_auto_router_id in ospf_cfg
    step('### 2. Test that manually set router-id overrides automatically assigned ###')
    sw("router-id %s" % ospf_man_router_id)
    ospf_cfg = sw("do show ip ospf")
    assert "Router ID:  %s" % ospf_man_router_id in ospf_cfg
    step('### Router-id is correct, test passed ###')
