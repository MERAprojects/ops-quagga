#!/usr/bin/python

# (c) Copyright 2016 Hewlett Packard Enterprise Development LP
#
# GNU Zebra is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2, or (at your option) any
# later version.
#
# GNU Zebra is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Zebra; see the file COPYING.  If not, write to the Free
# Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.


from route_generator_and_stats_reporter import (
    get_static_route_dict,
    capture_output_samples_and_generate_perf_stats
)
from time import sleep

TOPOLOGY = """
# +-------+    +-------+
# |       |    |       |
# |       <---->       |
# |  sw1  |    |  sw2  |
# |       |    |       |
# |       |    |       |
# +-------+    +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2

# Links
sw1:if01 -- sw2:if01
sw1:if02 -- sw2:if02
sw1:if03 -- sw2:if03
sw1:if04 -- sw2:if04
"""


# The number of routes under test should be greater than the batch size
# being used within zebra
MAX_IPV6_ROUTE = 250
TOTAL_TIME = 8
SAMPLING_TIME = 2
TRIGGER_SLEEP = 5
SNAPSHOT_TIME = 2 * SAMPLING_TIME
zebra_stop_command_string = "systemctl stop ops-zebra"
zebra_start_command_string = "systemctl start ops-zebra"


def ConfigureIpv6StaticRoutes(sw1, sw2, ipv6_route_list, step):
    sw1_interfaces = []

    # IPv4 addresses to cnfigure on switch
    sw1_if_ip = "8421:8421::1"
    sw1_mask = 64
    sw1_interface = sw1.ports["if0{}".format(1)]

    step("Configuring interface and IPv6 on SW1")

    # COnfiguring interfaces with its respective addresses and enables
    sw1("configure terminal")

    sw1("interface {}".format(sw1_interface))
    sw1("ipv6 address {}/{}".format(sw1_if_ip, sw1_mask))
    sw1("no shutdown")
    sw1("exit")

    output = sw1("do show running-config")
    assert "interface {}".format(sw1_interface) in output
    assert "ipv6 address {}/{}".format(sw1_if_ip, sw1_mask) in output

    step('### Configuration on sw1 and sw2 complete ###\n')

    # Stop ops-zebra process on sw1
    sw1(zebra_stop_command_string, shell='bash')

    for route in ipv6_route_list:
        sw1("ipv6 route {} {}".format(route['Prefix'], route['Nexthop']))

    sw1("exit")

    step('### Static routes configured on sw1 ###\n')

    # Start ops-zebra process on sw1
    sw1(zebra_start_command_string, shell='bash')

    sleep(TRIGGER_SLEEP)

    perf_stats_dict = capture_output_samples_and_generate_perf_stats(
                                       sw1, ipv6_route_list,
                                       "Config", False,
                                       TOTAL_TIME, SAMPLING_TIME,
                                       SNAPSHOT_TIME)

    assert perf_stats_dict is not None, "No perf stat captured \
           at "  + str(SNAPSHOT_TIME) + "seconds"

    assert perf_stats_dict['TotalShowIpRoute'] == MAX_IPV6_ROUTE,  "The \
           show ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalShowIpRoute'])

    assert perf_stats_dict['TotalKernelIpRoute'] == MAX_IPV6_ROUTE,  "The \
           kernel ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalKernelIpRoute'])

    assert perf_stats_dict['TotalShowRunning'] == MAX_IPV6_ROUTE,  "The \
           show running captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalShowRunning'])


def InterfaceDown(sw1, sw2, ipv6_route_list, step):
    step('### Test selection of static routes on interface shutdown ###')

    sw1_interface = sw1.ports["if0{}".format(1)]

    sw1("configure terminal")

    sw1("interface {}".format(sw1_interface))
    sw1("shutdown")
    sw1("exit")

    sw1("exit")

    sleep(TRIGGER_SLEEP)

    perf_stats_dict= capture_output_samples_and_generate_perf_stats(
                                     sw1, ipv6_route_list,
                                     "Interface shutdown", False,
                                     TOTAL_TIME, SAMPLING_TIME,
                                     SNAPSHOT_TIME)

    assert perf_stats_dict is not None, "No perf stat captured \
           at "  + str(SNAPSHOT_TIME) + "seconds"

    assert perf_stats_dict['TotalShowIpRoute'] == 0,  "The \
           show ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(0) + " \
           actual: " + str(perf_stats_dict['TotalShowIpRoute'])

    assert perf_stats_dict['TotalKernelIpRoute'] == 0,  "The \
           kernel ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(0) + " \
           actual: " + str(perf_stats_dict['TotalKernelIpRoute'])

    assert perf_stats_dict['TotalShowRunning'] == MAX_IPV6_ROUTE,  "The \
           show running captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalShowRunning'])


def InterfaceUp(sw1, sw2, ipv6_route_list, step):
    step('### Test selection of static routes on interface un-shutdown ###')

    sw1_interface = sw1.ports["if0{}".format(1)]

    sw1("configure terminal")

    sw1("interface {}".format(sw1_interface))
    sw1("no shutdown")
    sw1("exit")

    sw1("exit")

    sleep(TRIGGER_SLEEP)

    perf_stats_dict = capture_output_samples_and_generate_perf_stats(
                                     sw1, ipv6_route_list,
                                     "Interface un-shutdown", False,
                                     TOTAL_TIME, SAMPLING_TIME,
                                     SNAPSHOT_TIME)

    assert perf_stats_dict is not None, "No perf stat captured \
           at "  + str(SNAPSHOT_TIME) + "seconds"

    assert perf_stats_dict['TotalShowIpRoute'] == MAX_IPV6_ROUTE,  "The \
           show ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalShowIpRoute'])

    assert perf_stats_dict['TotalKernelIpRoute'] == MAX_IPV6_ROUTE,  "The \
           kernel ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalKernelIpRoute'])

    assert perf_stats_dict['TotalShowRunning'] == MAX_IPV6_ROUTE,  "The \
           show running captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalShowRunning'])


def InterfaceAddrChange(sw1, sw2, ipv6_route_list, step):
    step('### Test selection of static routes on interface address change ###')

    sw1_interface = sw1.ports["if0{}".format(1)]

    sw1("configure terminal")

    sw1("interface {}".format(sw1_interface))
    sw1("ipv6 address {}/{}".format("9421:9421::1", "64"))
    sw1("exit")

    sw1("exit")

    sleep(TRIGGER_SLEEP)

    perf_stats_dict = capture_output_samples_and_generate_perf_stats(
                                     sw1, ipv6_route_list,
                                     "Interface address change", False,
                                     TOTAL_TIME, SAMPLING_TIME,
                                     SNAPSHOT_TIME)

    assert perf_stats_dict is not None, "No perf stat captured \
           at "  + str(SNAPSHOT_TIME) + "seconds"

    assert perf_stats_dict['TotalShowIpRoute'] == MAX_IPV6_ROUTE,  "The \
           show ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalShowIpRoute'])

    assert perf_stats_dict['TotalKernelIpRoute'] == MAX_IPV6_ROUTE,  "The \
           kernel ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalKernelIpRoute'])

    assert perf_stats_dict['TotalShowRunning'] == MAX_IPV6_ROUTE,  "The \
           show running captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalShowRunning'])


def InterfaceAddrRestore(sw1, sw2, ipv6_route_list, step):
    step('### Test selection of static routes on interface address restore ###')

    sw1_interface = sw1.ports["if0{}".format(1)]

    sw1("configure terminal")

    sw1("interface {}".format(sw1_interface))
    sw1("ipv6 address {}/{}".format("8421:8421::1", "64"))
    sw1("exit")

    sw1("exit")

    sleep(TRIGGER_SLEEP)

    perf_stats_dict = capture_output_samples_and_generate_perf_stats(
                                     sw1, ipv6_route_list,
                                     "Interface address restore", False,
                                     TOTAL_TIME, SAMPLING_TIME,
                                     SNAPSHOT_TIME)

    assert perf_stats_dict is not None, "No perf stat captured \
           at "  + str(SNAPSHOT_TIME) + "seconds"

    assert perf_stats_dict['TotalShowIpRoute'] == MAX_IPV6_ROUTE,  "The \
           show ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalShowIpRoute'])

    assert perf_stats_dict['TotalKernelIpRoute'] == MAX_IPV6_ROUTE,  "The \
           kernel ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalKernelIpRoute'])

    assert perf_stats_dict['TotalShowRunning'] == MAX_IPV6_ROUTE,  "The \
           show running captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(MAX_IPV6_ROUTE) + " \
           actual: " + str(perf_stats_dict['TotalShowRunning'])


def InterfaceNoRouting(sw1, sw2, ipv6_route_list, step):
    step('### Test selection of static routes on interface no routing ###')

    sw1_interface = sw1.ports["if0{}".format(1)]

    sw1("configure terminal")

    sw1("interface {}".format(sw1_interface))
    sw1("no routing")
    sw1("exit")

    sw1("exit")

    sleep(TRIGGER_SLEEP)

    perf_stats_dict = capture_output_samples_and_generate_perf_stats(
                                     sw1, ipv6_route_list,
                                     "Interface no routing", False,
                                     TOTAL_TIME, SAMPLING_TIME,
                                     SNAPSHOT_TIME)

    assert perf_stats_dict is not None, "No perf stat captured \
           at "  + str(SNAPSHOT_TIME) + "seconds"

    assert perf_stats_dict['TotalShowIpRoute'] == 0,  "The \
           show ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(0) + " \
           actual: " + str(perf_stats_dict['TotalShowIpRoute'])

    assert perf_stats_dict['TotalKernelIpRoute'] == 0,  "The \
           kernel ip route captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(0) + " \
           actual: " + str(perf_stats_dict['TotalKernelIpRoute'])

    assert perf_stats_dict['TotalShowRunning'] == 0,  "The \
           show running captured at " + str(SNAPSHOT_TIME) + " seconds \
           are not same expected: " + str(0) + " \
           actual: " + str(perf_stats_dict['TotalShowRunning'])


def test_zebra_ct_ipv6_scale_tests(topology, step):
    sw1 = topology.get("sw1")
    sw2 = topology.get("sw2")
    ipv6_route_list = get_static_route_dict(MAX_IPV6_ROUTE, False, '1')

    assert sw1 is not None
    assert sw2 is not None

    ConfigureIpv6StaticRoutes(sw1, sw2, ipv6_route_list, step)
    InterfaceDown(sw1, sw2, ipv6_route_list, step)
    InterfaceUp(sw1, sw2, ipv6_route_list, step)
    InterfaceAddrChange(sw1, sw2, ipv6_route_list, step)
    InterfaceAddrRestore(sw1, sw2, ipv6_route_list, step)
    InterfaceNoRouting(sw1, sw2, ipv6_route_list, step)
