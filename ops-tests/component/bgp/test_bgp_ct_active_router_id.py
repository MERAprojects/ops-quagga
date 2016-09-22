# -*- coding: utf-8 -*-

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


TOPOLOGY = """
#
#+-------+
#|  sw1  |
#+-------+
#

# Nodes
[type=openswitch name="Switch 1"] sw1

"""
from time import sleep

#  This is basic configuration required for the test, it verifies bgp
#  deamon is running and configures bgp router without the router-id
#  and one interface with IPv4 address.
def configure_bgp_router_without_router_id(sw1, step):
    bgp_asn = "10"
    bgp_interface1 = "9.0.0.1"
    bgp_network = "11.0.0.0"
    bgp_pl = "8"

    step("1-Verifying bgp processes...")
    pid = sw1("pgrep -f bgpd", shell='bash')
    pid = pid.strip()
    assert pid != "" and pid is not None

    step("2-Applying BGP configurations without router id")
    sw1("configure terminal")
    sw1("router bgp {}".format(bgp_asn))
    sw1("network {}/{}".format(bgp_network, bgp_pl))
    sw1("exit")
    sw1("interface 1")
    sw1("no shutdown")
    sw1("ip address {}/{}".format(bgp_interface1, bgp_pl))
    sw1("exit")
    sw1("end")
    sleep(1)

#  This test verifies BGP router_id is same as the interface 1
#  IPv4 address.
def verify_bgp_router_id_is_interface_ip(sw1, step):
    bgp_router_id1 = "9.0.0.1"
    step("3-Verifying BGP Router-ID is the interface 1 ip")
    output = sw1("show ip bgp summary")
    assert bgp_router_id1 in output

#  This test verifies that unconfiguring the L3 interface which was
#  used as BGP router_id changes it to any other available L3
#  interface IPv4 address
def verify_interface_removed(sw1, step):
    bgp_pl = "8"
    bgp_interface1 = "9.0.0.1"
    bgp_interface2 = "9.0.0.2"
    bgp_router_id2 = "9.0.0.2"
    step("4-Verify removing interface changes the BGP router-id")
    sw1("configure terminal")
    sw1("interface 1")
    sw1("shutdown")
    sw1("no ip address {}/{}".format(bgp_interface1, bgp_pl))
    sw1("exit")
    sw1("interface 2")
    sw1("no shutdown")
    sw1("ip address {}/{}".format(bgp_interface2, bgp_pl))
    sw1("exit")
    sw1("end")
    sleep(1)
    output = sw1("show ip bgp summary")
    assert bgp_router_id2 in output

#  This test verifies that the user configured BGP router level router-id
#  gets precedence over system identified router-id from L3 interfaces.
def verify_configured_bgp_router_id(sw1, step):
    bgp_asn = "10"
    user_cfg_bgp_router_id = "9.0.0.3"
    step("5-Verify configuring BGP router-id gets more precedence")
    sw1("configure terminal")
    sw1("router bgp {}".format(bgp_asn))
    sw1("bgp router-id {}".format(user_cfg_bgp_router_id))
    sw1("exit")
    sw1("end")
    sleep(1)
    output = sw1("show ip bgp summary")
    assert user_cfg_bgp_router_id in output

#  This test verifies that the user unconfiguring BGP router-id
#  sets it to zero.
def verify_unconfiguring_bgp_router_id(sw1, step):
    bgp_asn = "10"
    bgp_router_id2 = "0.0.0.0"
    step("6-Verify unconfiguring BGP router-id sets it to null")
    sw1("configure terminal")
    sw1("router bgp {}".format(bgp_asn))
    sw1("no bgp router-id")
    sw1("exit")
    sw1("end")
    sleep(1)
    output = sw1("show ip bgp summary")
    assert bgp_router_id2 in output

def test_bgp_ct_active_router_id(topology, step):
    sw1 = topology.get("sw1")
    assert sw1 is not None
    configure_bgp_router_without_router_id(sw1, step)
    verify_bgp_router_id_is_interface_ip(sw1, step)
    verify_interface_removed(sw1, step)
    verify_configured_bgp_router_id(sw1, step)
    verify_unconfiguring_bgp_router_id(sw1, step)
