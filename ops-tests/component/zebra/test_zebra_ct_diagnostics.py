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

from pytest import mark
from zebra_routing import (
    ZEBRA_DEFAULT_TIMEOUT
)

"""
Component test to verify zebra diagnostic commands.
"""

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
@mark.gate
def test_zebra_diag_dump(topology, step):
    '''
    This test verifies various diagnostic commands related to zebra daemon
    by verifying if the output of the commands have the expected keywords.
    '''
    sw1 = topology.get('sw1')

    assert sw1 is not None

    step('### Testing output of "ovs-appctl -t ops-zebra zebra/dump rib" ###')
    output = sw1("ovs-appctl -t ops-zebra zebra/dump rib", shell="bash")
    assert '-------- Zebra internal IPv4 routes dump: --------' in output, \
           'Missing internal IPv4 routes dump in "zebra/dump rib" output'
    assert '-------- Zebra internal IPv6 routes dump: --------' in output, \
           'Missing internal IPv6 routes dump in "zebra/dump rib" output'

    step(
        '### Testing output of "ovs-appctl -t ops-zebra zebra/dump '
        'kernel-routes" ###')
    output = sw1(
        "ovs-appctl -t ops-zebra zebra/dump kernel-routes",
        shell="bash")
    assert '-------- Kernel IPv4 routes dump: --------' in output, \
           'Missing kernel IPv4 routes dump in "zebra/dump kernel-routes" ' \
           'output'
    assert '-------- Kernel IPv6 routes dump: --------' in output, \
           'Missing kernel IPv6 routes dump in "zebra/dump kernel-routes" ' \
           'output'

    step(
        '### Testing output of "ovs-appctl -t ops-zebra zebra/dump '
        'l3-port-cache" ###')
    output = sw1(
        "ovs-appctl -t ops-zebra zebra/dump l3-port-cache",
        shell="bash")
    assert '-------- Zebra L3 port cache dump: --------' in output, \
           'Missing L3 port cache dump in "zebra/dump l3-port-cache" output'

    step(
        '### Testing output of "ovs-appctl -t ops-zebra zebra/dump memory" '
        '###')
    output = sw1("ovs-appctl -t ops-zebra zebra/dump memory", shell="bash")
    assert '-------- Zebra memory dump: --------' in output, \
           'Missing memory dump in "zebra/dump memory" output'

    step(
        '### Testing output of CLI command "diag-dump route-manager basic" '
        '###')
    output = sw1('diag-dump route-manager basic')
    assert '-------- Zebra internal IPv4 routes dump: --------' in output, \
           'Missing internal IPv4 routes dump in "diag-dump route-manager ' \
           'basicb" output'
    assert '-------- Zebra internal IPv6 routes dump: --------' in output, \
           'Missing internal IPv6 routes dump in "diag-dump route-manager ' \
           'basic" output'
    assert '-------- Kernel IPv4 routes dump: --------' in output, \
           'Missing kernel IPv4 routes dump in "diag-dump route-manager ' \
           'basic" output'
    assert '-------- Kernel IPv6 routes dump: --------' in output, \
           'Missing kernel IPv6 routes dump in "diag-dump route-manager ' \
           'basic" output'
    assert '-------- Zebra L3 port cache dump: --------' in output, \
           'Missing L3 port cache dump in "diag-dump route-manager basic" ' \
           'output'
    assert '-------- Zebra memory dump: --------' in output, \
           'Missing memory dump in "diag-dump route-manager basic" output'

    step(
        '### Testing invalid option to "ovs-appctl -t ops-zebra zebra/dump" '
        'command ###')
    output = sw1(
        "ovs-appctl -t ops-zebra zebra/dump unsupported",
        shell="bash")
    assert 'Argument unsupported not supported' in output, \
           '"zebra/dump unsupported" should fail with error'

    step(
        '### Testing output of "ovs-appctl -t ops-zebra zebra/dump" with no '
        'arguments ###')
    output = sw1("ovs-appctl -t ops-zebra zebra/dump", shell="bash")
    assert '-------- Zebra internal IPv4 routes dump: --------' in output, \
           'Missing internal IPv4 routes dump in "zebra/dump" output'
    assert '-------- Zebra internal IPv6 routes dump: --------' in output, \
           'Missing internal IPv6 routes dump in "zebra/dump" output'
    assert '-------- Kernel IPv4 routes dump: --------' in output, \
           'Missing kernel IPv4 routes dump in "zebra/dump" output'
    assert '-------- Kernel IPv6 routes dump: --------' in output, \
           'Missing kernel IPv6 routes dump in "zebra/dump" output'
    assert '-------- Zebra L3 port cache dump: --------' in output, \
           'Missing L3 port cache dump in "zebra/dump" output'
    assert '-------- Zebra memory dump: --------' in output, \
           'Missing memory dump in "zebra/dump" output'

    step('### Testing invalid arguments to "ovs-appctl -t ops-zebra zebra/debug" ###')
    output = sw1("ovs-appctl -t ops-zebra zebra/debug unsupported", shell="bash")
    assert 'Unsupported argument - unsupported' in output, \
           '"ovs-appctl -t ops-zebra zebra/debug" should fail with error'
