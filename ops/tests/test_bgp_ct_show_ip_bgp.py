#!/usr/bin/python

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

import pytest
from opsvsiutils.vtyshutils import *
from opsvsiutils.bgpconfig import *

#
# This case tests the most basic configuration between two BGP instances by
# verifying that the advertised routes are received on both instances running
# BGP. Once peering is established, show ip bgp and show ip bgp <route>
# is tested.
#
# The following commands are tested:
#   * router bgp <asn>
#   * bgp router-id <router-id>
#   * network <network>
#   * neighbor <peer> remote-as <asn>
#   * show ip bgp
#   * show ip bgp <route>
#
# S1 [interface 1]<-->S2 [interface 1]
#

BGP1_ASN = "1"
BGP1_ROUTER_ID = "9.0.0.1"
BGP1_NETWORK = "11.0.0.0"

BGP2_ASN = "2"
BGP2_ROUTER_ID = "9.0.0.2"
BGP2_NETWORK = "12.0.0.0"

BGP1_NEIGHBOR = BGP2_ROUTER_ID
BGP1_NEIGHBOR_ASN = BGP2_ASN

BGP2_NEIGHBOR = BGP1_ROUTER_ID
BGP2_NEIGHBOR_ASN = BGP1_ASN

BGP_NETWORK_PL = "8"
BGP_NETWORK_MASK = "255.0.0.0"
BGP_ROUTER_IDS = [BGP1_ROUTER_ID, BGP2_ROUTER_ID]

BGP1_CONFIG = ["router bgp %s" % BGP1_ASN,
               "bgp router-id %s" % BGP1_ROUTER_ID,
               "network %s/%s" % (BGP1_NETWORK, BGP_NETWORK_PL),
               "neighbor %s remote-as %s" % (BGP1_NEIGHBOR, BGP1_NEIGHBOR_ASN)]

BGP2_CONFIG = ["router bgp %s" % BGP2_ASN,
               "bgp router-id %s" % BGP2_ROUTER_ID,
               "network %s/%s" % (BGP2_NETWORK, BGP_NETWORK_PL),
               "neighbor %s remote-as %s" % (BGP2_NEIGHBOR, BGP2_NEIGHBOR_ASN)]

BGP_CONFIGS = [BGP1_CONFIG, BGP2_CONFIG]

NUM_OF_SWITCHES = 2
NUM_HOSTS_PER_SWITCH = 0

SWITCH_PREFIX = "s"


class myTopo(Topo):
    def build(self, hsts=0, sws=2, **_opts):
        self.hsts = hsts
        self.sws = sws

        switch = self.addSwitch("%s1" % SWITCH_PREFIX)
        switch = self.addSwitch(name="%s2" % SWITCH_PREFIX,
                                cls=PEER_SWITCH_TYPE,
                                **self.sopts)

        # Connect the switches
        for i in irange(2, sws):
            self.addLink("%s%s" % (SWITCH_PREFIX, i-1),
                         "%s%s" % (SWITCH_PREFIX, i))


class bgpTest(OpsVsiTest):
    def setupNet(self):
        self.net = Mininet(topo=myTopo(hsts=NUM_HOSTS_PER_SWITCH,
                                       sws=NUM_OF_SWITCHES,
                                       hopts=self.getHostOpts(),
                                       sopts=self.getSwitchOpts()),
                           switch=SWITCH_TYPE,
                           host=OpsVsiHost,
                           link=OpsVsiLink,
                           controller=None,
                           build=True)

    def configure_switch_ips(self):
        info("\n########## Configuring switch IPs.. ##########\n")

        i = 0
        for switch in self.net.switches:
            # Configure the IPs between the switches
            if isinstance(switch, VsiOpenSwitch):
                switch.cmdCLI("configure terminal")
                switch.cmdCLI("interface 1")
                switch.cmdCLI("no shutdown")
                switch.cmdCLI("ip address %s/%s" % (BGP_ROUTER_IDS[i],
                                                    BGP_NETWORK_PL))
                switch.cmdCLI("exit")
            else:
                switch.setIP(ip=BGP_ROUTER_IDS[i],
                             intf="%s-eth1" % switch.name)
            i += 1

    def verify_bgp_running(self):
        info("\n########## Verifying bgp processes.. ##########\n")

        for switch in self.net.switches:
            pid = switch.cmd("pgrep -f bgpd").strip()
            assert (pid != ""), "bgpd process not running on switch %s" % \
                                switch.name

            info("### bgpd process exists on switch %s ###\n" % switch.name)

    def configure_bgp(self):
        info("\n########## Applying BGP configurations... ##########\n")

        i = 0
        for switch in self.net.switches:
            info("### Applying BGP config on switch %s ###\n" % switch.name)
            cfg_array = BGP_CONFIGS[i]
            i += 1

            SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

    def verify_bgp_route_removed(self):
        info("\n########## Verifying route from BGP1 removed... ##########\n")

        switch = self.net.switches[1]
        network = BGP1_NETWORK
        next_hop = BGP1_ROUTER_ID
        verify_route_exists = False

        info("### Verifying show ip bgp ###\n")
        found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop,
                                                verify_route_exists)

        assert not found, "Route (%s) was not successfully removed" % network

        # Verify show ip bgp <route> cmd
        info("### Verifying show ip bgp %s ###\n" % network)
        found = SwitchVtyshUtils.verify_show_ip_bgp_route(switch, network,
                                                          next_hop)

        assert not found, "Route (%s) was not successfully removed" % network

    def verify_bgp_routes(self):
        info("\n########## Verifying Routes via show ip bgp.. ##########\n")

        self.verify_bgp_route(self.net.switches[0], BGP2_NETWORK,
                              BGP2_ROUTER_ID)
        self.verify_bgp_route(self.net.switches[1], BGP1_NETWORK,
                              BGP1_ROUTER_ID)

    def verify_configs(self):
        info("\n########## Verifying all configurations.. ##########\n")

        for i in range(0, len(BGP_CONFIGS)):
            bgp_cfg = BGP_CONFIGS[i]
            switch = self.net.switches[i]

            for cfg in bgp_cfg:
                res = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg])
                assert res, "Config \"%s\" was not correctly configured!" % cfg

    def verify_bgp_route(self, switch, network, next_hop):
        found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

        assert found, "Could not find route (%s -> %s) on %s" % \
                      (network, next_hop, switch.name)

    def verify_show_ip_bgp_route(self):
        info("\n########## Verifying show ip bgp route ##########\n")
        switch = self.net.switches[0]

        info("### Verifying Negative Case ###\n")
        network = "1.1.1.0"
        next_hop = "1.1.1.1"
        found = SwitchVtyshUtils.verify_show_ip_bgp_route(switch, network,
                                                          next_hop)
        assert not found, "found route (%s -> %s) on %s" % \
                          (network, next_hop, switch.name)

        info("### Verifying Positive Case ###\n")
        network = BGP2_NETWORK
        next_hop = BGP2_ROUTER_ID
        found = SwitchVtyshUtils.verify_show_ip_bgp_route(switch, network,
                                                          next_hop)
        assert found, "Could not find route (%s -> %s) on %s" % \
                      (network, next_hop, switch.name)

    def unconfigure_network_bgp(self):
        info("\n########## Unconfiguring BGP network ##########\n")

        switch = self.net.switches[0]
        cfg_array = []
        cfg_array.append("router bgp %s" % BGP1_ASN)
        cfg_array.append("no neighbor %s" % BGP1_NEIGHBOR)

        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)


class Test_bgpd_show_ip_bgp:
    def setup(self):
        pass

    def teardown(self):
        pass

    def setup_class(cls):
        Test_bgpd_show_ip_bgp.test_var = bgpTest()

    def teardown_class(cls):
        Test_bgpd_show_ip_bgp.test_var.net.stop()

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def __del__(self):
        del self.test_var

    def test_bgp_full(self):
        self.test_var.configure_switch_ips()
        self.test_var.verify_bgp_running()
        self.test_var.configure_bgp()
        self.test_var.verify_configs()
        self.test_var.verify_bgp_routes()
        self.test_var.verify_show_ip_bgp_route()
        self.test_var.unconfigure_network_bgp()
        self.test_var.verify_bgp_route_removed()
