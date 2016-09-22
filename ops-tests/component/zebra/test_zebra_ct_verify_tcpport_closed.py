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


from zebra_routing import (
    ZEBRA_DEFAULT_TIMEOUT
)
from pytest import mark

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


@mark.timeout(ZEBRA_DEFAULT_TIMEOUT)
def test_zebra_ct_verify_tcpport_closed(topology, step):
    '''
    This test verifies if the TCP port: 2601 used by OpenSource Zebra protocol
    is kept closed as it is not implemented in the OpenSwitch product
    '''
    sw1 = topology.get('sw1')

    assert sw1 is not None

    step('### Test to verify whether TCP port: 2601 used by OpenSource zebra '
         'protocol is kept closed  ###')
    step('### Executing system command: "ip netns exec swns netstat -pant" '
         ' to get the open TCP ports ###')

    ret = sw1("ip netns exec swns netstat -pant", shell='bash')
    assert "2601" not in ret, "TCP port: 2601 is detected open"

    step('### TCP port: 2601 not detected open, Test passed ###')
