# -*- coding: utf-8 -*-

# (c) Copyright 2015 Hewlett Packard Enterprise Development LP
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

from time import sleep
import pytest

TOPOLOGY = """
#                +-------+
#     +---------->  sw2  <----------+
#     |          +-------+          |
#     |                             |
# +---v---+      +-------+      +---v---+
# |  sw1  <------>  sw3  <------>  sw5  |
# +---^---+      +-------+      +---^---+
#     |                             |
#     |          +-------+          |
#     +---------->  sw4  <----------+
#                +-------+

# Nodes
[type=openswitch name="Switch 1"] sw1
[type=openswitch name="Switch 2"] sw2
[type=openswitch name="Switch 3"] sw3
[type=openswitch name="Switch 4"] sw4
[type=openswitch name="Switch 5"] sw5


# Links
sw1:if01 -- sw2:if01
sw1:if02 -- sw3:if01
sw1:if03 -- sw4:if01
sw5:if01 -- sw2:if02
sw5:if02 -- sw3:if02
sw5:if03 -- sw4:if02
"""


bgp1_asn = "1"
bgp1_router_id = "9.0.0.1"
bgp1_network = "11.0.0.0"

bgp2_asn = "2"
bgp2_router_id = "9.0.0.2"
bgp2_network = "12.0.0.0"

bgp3_asn = "3"
bgp3_router_id = "9.0.0.3"
bgp3_network = "12.0.0.0"

bgp4_asn = "4"
bgp4_router_id = "9.0.0.4"
bgp4_network = "12.0.0.0"

bgp5_asn = "5"
bgp5_router_id = "9.0.0.5"
bgp5_network = "12.0.0.0"

# S1 Neighbors
bgp1_neighbor1 = "10.10.10.2"
bgp1_neighbor1_asn = bgp2_asn
bgp1_intf1_ip = "10.10.10.1"

bgp1_neighbor2 = "20.20.20.2"
bgp1_neighbor2_asn = bgp3_asn
bgp1_intf2_ip = "20.20.20.1"

bgp1_neighbor3 = "30.30.30.2"
bgp1_neighbor3_asn = bgp4_asn
bgp1_intf3_ip = "30.30.30.1"

# S2 Neighbors
bgp2_neighbor1 = "10.10.10.1"
bgp2_neighbor1_asn = bgp1_asn
bgp2_intf1_ip = "10.10.10.2"

bgp2_neighbor2 = "40.40.40.2"
bgp2_neighbor2_asn = bgp5_asn
bgp2_intf2_ip = "40.40.40.1"

# S3 Neighbors
bgp3_neighbor1 = "20.20.20.1"
bgp3_neighbor1_asn = bgp1_asn
bgp3_intf1_ip = "20.20.20.2"

bgp3_neighbor2 = "50.50.50.2"
bgp3_neighbor2_asn = bgp5_asn
bgp3_intf2_ip = "50.50.50.1"

# S4 neighbors
bgp4_neighbor1 = "30.30.30.1"
bgp4_neighbor1_asn = bgp1_asn
bgp4_intf1_ip = "30.30.30.2"

bgp4_neighbor2 = "60.60.60.2"
bgp4_neighbor2_asn = bgp5_asn
bgp4_intf2_ip = "60.60.60.1"

# S5 Neighbors
bgp5_neighbor1 = "40.40.40.1"
bgp5_neighbor1_asn = bgp2_asn
bgp5_intf1_ip = "40.40.40.2"

bgp5_neighbor2 = "50.50.50.1"
bgp5_neighbor2_asn = bgp3_asn
bgp5_intf2_ip = "50.50.50.2"

bgp5_neighbor3 = "60.60.60.1"
bgp5_neighbor3_asn = bgp4_asn
bgp5_intf3_ip = "60.60.60.2"

bgp_intf_ip_arr = [[bgp1_intf1_ip, bgp1_intf2_ip, bgp1_intf3_ip],
                   [bgp2_intf1_ip, bgp2_intf2_ip],
                   [bgp3_intf1_ip, bgp3_intf2_ip],
                   [bgp4_intf1_ip, bgp4_intf2_ip],
                   [bgp5_intf1_ip, bgp5_intf2_ip, bgp5_intf3_ip]]

bgp_network_pl = "8"
bgp_network_mask = "255.0.0.0"
bgp_router_ids = [bgp1_router_id, bgp2_router_id, bgp3_router_id,
                  bgp4_router_id, bgp5_router_id]

bgp_max_paths = 5

bgp1_config = ["router bgp {}".format(bgp1_asn),
               "bgp router-id {}".format(bgp1_router_id),
               "network {}/{}".format(bgp1_network, bgp_network_pl),
               "neighbor {} remote-as {}".format(bgp1_neighbor1,
                                                 bgp1_neighbor1_asn),
               "neighbor {} remote-as {}".format(bgp1_neighbor2,
                                                 bgp1_neighbor2_asn),
               "neighbor {} remote-as {}".format(bgp1_neighbor3,
                                                 bgp1_neighbor3_asn),
               "maximum-paths {}".format(bgp_max_paths)]

bgp2_config = ["router bgp {}".format(bgp2_asn),
               "bgp router-id {}".format(bgp2_router_id),
               "neighbor {} remote-as {}".format(bgp2_neighbor1,
                                                 bgp2_neighbor1_asn),
               "neighbor {} remote-as {}".format(bgp2_neighbor2,
                                                 bgp2_neighbor2_asn)]

bgp3_config = ["router bgp {}".format(bgp3_asn),
               "bgp router-id {}".format(bgp3_router_id),
               "neighbor {} remote-as {}".format(bgp3_neighbor1,
                                                 bgp3_neighbor1_asn),
               "neighbor {} remote-as {}".format(bgp3_neighbor2,
                                                 bgp3_neighbor2_asn)]

bgp4_config = ["router bgp {}".format(bgp4_asn),
               "bgp router-id {}".format(bgp4_router_id),
               "neighbor {} remote-as {}".format(bgp4_neighbor1,
                                                 bgp4_neighbor1_asn),
               "neighbor {} remote-as {}".format(bgp4_neighbor2,
                                                 bgp4_neighbor2_asn)]

bgp5_config = ["router bgp {}".format(bgp5_asn),
               "bgp router-id {}".format(bgp5_router_id),
               "network {}/{}".format(bgp5_network, bgp_network_pl),
               "neighbor {} remote-as {}".format(bgp5_neighbor1,
                                                 bgp5_neighbor1_asn),
               "neighbor {} remote-as {}".format(bgp5_neighbor2,
                                                 bgp5_neighbor2_asn),
               "neighbor {} remote-as {}".format(bgp5_neighbor3,
                                                 bgp5_neighbor3_asn)]

bgp_configs = [bgp1_config, bgp2_config, bgp3_config, bgp4_config, bgp5_config]

max_rte_veri_attemps = 300
cmd_route = "do show rib"


def verify_bgp_route(switch, network, next_hop):
    route_max_wait_time = max_rte_veri_attemps
    route_exists = False
    while route_max_wait_time > 0 and not route_exists:
        output = switch("do show ip bgp")
        lines = output.split("\n")
        for line in lines:
            if network in line and next_hop in line:
                print("Line:", line)
                route_exists = True
                break
        sleep(1)
        route_max_wait_time -= 1
        print("Wait time:", route_max_wait_time)
    return route_exists


# sw1 is harcoded
def configure_maxpaths(max_path, sw1):
    sw1("router bgp {}".format(bgp1_asn))
    if(max_path):
        sw1("maximum-paths 5")
        print("Verifying maximum-paths configured")
        output = sw1("do sh run")
        assert "maximum-paths 5" in output
    else:
        sw1("no maximum-paths")
        print("Verifying maximum-paths config removed")
        output = sw1("do sh run")
        assert "maximum-paths 5" not in output


def configure_ecmp(ecmp_status, sw1):
    if ecmp_status:
        sw1("no ip ecmp disable")
        print("Verifying ecmp is enabled")
        output = sw1("do show run")
        assert "ip ecmp disable" not in output
    else:
        sw1("ip ecmp disable")
        print("Verifying ecmp disabled")
        output = sw1("do show run")
        assert "ip ecmp disable" in output


def verify_maxpaths_ecmp_disabled(change_maxpaths, maxpaths_enabled, sw1):
    # Disable ecmp_config
    # Configure maxpath if applied
    # Verify global route if it has only 1 route
    print("Verifying maxpaths - ecmp disabled")
    configure_ecmp(False, sw1)
    if change_maxpaths:
        if maxpaths_enabled:
            configure_maxpaths(True, sw1)
        else:
            configure_maxpaths(False, sw1)
    print("Verify if ip route show 1 paths")
    verify_num_ip_route_exist_in_bgp1(1, sw1)


def verify_maxpaths_ecmp_enabled(change_maxpaths, maxpaths_enabled, sw1):
    # Enable ecmp_config, configure maxpath if applies
    # If not, it expects maxpath set previously
    # Verify global route if it has 3 routes (>1 route) if maxpath is set
    # and 1 route if maxpath is unset
    print("Verifying maxpaths - ecmp enabled")
    configure_ecmp(True, sw1)
    no_paths = 3
    if change_maxpaths:
        if maxpaths_enabled:
            configure_maxpaths(True, sw1)
        else:
            configure_maxpaths(False, sw1)
            no_paths = 1
    print("Verify if ip route show {} paths".format(no_paths))
    verify_num_ip_route_exist_in_bgp1(no_paths, sw1)


def config_ecmp_only(sw1):
    # Disable ecmp, expecting 1 path advertised
    # Enable ecmp, expecting > 1 paths advertised
    verify_maxpaths_ecmp_disabled(False, False, sw1)
    verify_maxpaths_ecmp_enabled(False, False, sw1)


def config_both_ecmp_maxpath(sw1):
    # Test if changing both maxpath and ecmp causing any issue
    # Disable ecmp, set max paths = 5, expecting 1 path advertised
    # Enable ecmp, set no maxpath, expecting 1 path advertised
    verify_maxpaths_ecmp_disabled(True, True, sw1)
    verify_maxpaths_ecmp_enabled(True, False, sw1)


# sw1 is harcoded
def get_number_of_paths_for_bgp1(sw1):
    route_step = sw1(cmd_route)
    multipath_count = 0
    if bgp1_neighbor1 in route_step:
        multipath_count += 1
    if bgp1_neighbor2 in route_step:
        multipath_count += 1
    if bgp1_neighbor3 in route_step:
        multipath_count += 1
    return multipath_count


def verify_num_ip_route_exist_in_bgp1(no_route, sw1):
    verification = False
    print("Verifying {} route(s) in {}".format(no_route, cmd_route))
    for i in range(max_rte_veri_attemps):
        multipath_count = get_number_of_paths_for_bgp1(sw1)
        print("Route Verification attempts {}".format(i))
        if multipath_count is no_route:
            verification = True
            break
        sleep(1)
    assert verification


# sw1 is harcoded
def verify_bgp_routes(sw1):
    print("Verifying routes exist")
    assert verify_bgp_route(sw1, bgp2_network, bgp1_neighbor1)
    assert verify_bgp_route(sw1, bgp3_network, bgp1_neighbor2)
    assert verify_bgp_route(sw1, bgp4_network, bgp1_neighbor3)


# sw1 is harcoded
def verify_max_paths(sw1):
    print("Verifying maximum-paths")
    verify_bgp_routes(sw1)
    print("Setting maximum-paths to 5")
    configure_maxpaths(True, sw1)
    print("Verifying that there are 3 multipaths")
    verify_num_ip_route_exist_in_bgp1(3, sw1)


def verify_no_max_paths(sw1):
    print("Verifying no maximum-paths")
    print("Setting no maximum-paths")
    configure_maxpaths(False, sw1)
    print("Verifying that there is only 1 path")
    verify_num_ip_route_exist_in_bgp1(1, sw1)


# sw1 is harcoded
def config_maxpath_only(sw1):
    # Ecmp is previously enabled (by default),
    # Configure only maxpath to 5 expecting > 1 paths advertised
    # Configure no maxpath, expecting 1 path advertised
    verify_max_paths(sw1)
    verify_no_max_paths(sw1)
    verify_max_paths(sw1)


def run_test(switches):
    print("Changing maxpaths only")
    config_maxpath_only(switches[0])
    print("Changing ecmp only")
    config_ecmp_only(switches[0])
    print("Changing ecmp and maxpaths")
    config_both_ecmp_maxpath(switches[0])


def loop_test(loop, switches):
    # Running loop to test stability and catching intermitten issue if any
    for i in range(loop):
        print("Test Loop {}".format(i))
        run_test(switches)


@pytest.mark.skipif(True, reason="Failing in both frameworks when verifying"
                                 "'verify_bgp_route(sw1, bgp4_network,"
                                 "                  bgp1_neighbor3)'")
def test_bgp_ct_maximum_paths(topology, step):
    switches = []
    for index in range(1, 6):
        switches.append(topology.get("sw{}".format(index)))
    step("1-Configuring switch IPs...")
    i = 0
    for switch in switches:
        # Configure the IPs between the switches
        j = 1
        switch("configure terminal")
        for ip_addr in bgp_intf_ip_arr[i]:
            switch("interface {}".format(j))
            switch("no shutdown")
            switch("ip address {}/{}".format(ip_addr, bgp_network_pl))
            switch("exit")
            j += 1
        i += 1
    step("2-Verifying bgp processes...")
    for switch in switches:
        pid = switch("pgrep -f bgpd", shell='bash')
        pid = pid.strip()
        assert pid != "" and pid is not None
    step("3-Configuring BGP on all switches...")
    i = 0
    for switch in switches:
        configs = bgp_configs[i]
        i += 1
        for config in configs:
            switch(config)
    step("4-Verifying all configurations...")
    for i in range(5):
        configs = bgp_configs[i]
        switch = switches[i]
        output = switch("do show run")
        for config in configs:
            assert config in output
    loop_test(1, switches)
