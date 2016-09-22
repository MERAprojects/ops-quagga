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
# Only one switch emulated for testing simple BGP configurations through vtysh.
# This test checks the following commands:
#   * router bgp <asn> # This is required, for testing the primary case;
#   * bgp router-id <router-id-value>
#   * network <network>
# Topology:
#   S1 [interface 1]
#

BGP_ASN = "1"
BGP_ROUTER_ID = "9.0.0.1"
BGP_NETWORK = "11.0.0.0"
BGP_PL = "8"
NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0
SWITCH_PREFIX = "s"


class myTopo(Topo):
    def build(self, hsts=0, sws=2, **_opts):
        self.hsts = hsts
        self.sws = sws

        for i in irange(1, sws):
            switch = self.addSwitch("%s%s" % (SWITCH_PREFIX, i))


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

        self.switch = self.net.switches[0]

    def verify_bgp_running(self):
        info("\n########## Verifying bgp process.. ##########\n")

        pid = self.switch.cmd("pgrep -f bgpd").strip()
        assert (pid != ""), "bgpd process not running on switch %s" % \
                            self.switch.name

        info("### bgpd process exists on switch %s ###\n" % self.switch.name)

    def configure_bgp(self):
        info("\n########## Applying BGP configurations... ##########\n")

        cfg_array = []
        cfg_array.append("router bgp %s" % BGP_ASN)
        cfg_array.append("bgp router-id %s" % BGP_ROUTER_ID)
        cfg_array.append("network %s/%s" % (BGP_NETWORK, BGP_PL))

        SwitchVtyshUtils.vtysh_cfg_cmd(self.switch, cfg_array)

    def verify_bgp_router_id(self):
        info("\n########## Verifying BGP Router-ID... ##########\n")

        config = "bgp router-id"
        res = SwitchVtyshUtils.verify_cfg_value(self.switch, [config],
                                                BGP_ROUTER_ID)
        assert res, "Config \"%s\" was not correctly configured!" % config

        info("### Config \"%s\" was correctly configured. ###\n" % config)

    def verify_bgp_route(self):
        info("\n########## Verifying routes... ##########\n")

        network = BGP_NETWORK
        next_hop = "0.0.0.0"

        found = SwitchVtyshUtils.wait_for_route(self.switch, network, next_hop)

        assert found, "Could not find route (%s -> %s) on %s" % \
                      (network, next_hop, self.switch.name)

        info("### Route exists ###\n")

    def verify_no_bgp_route(self):
        info("\n########## Verifying routes removed... ##########\n")

        network = BGP_NETWORK
        next_hop = "0.0.0.0"
        verify_route_exists = False

        found = SwitchVtyshUtils.wait_for_route(self.switch, network, next_hop,
                                                verify_route_exists)

        assert not found, "Route was not removed (%s -> %s) on %s" % \
                          (network, next_hop, self.switch.name)

        info("### Route successfully removed ###\n")

    def unconfigure_bgp(self):
        info("\n########## Unconfiguring bgp network ##########\n")

        cfg_array = []
        cfg_array.append("router bgp %s" % BGP_ASN)
        cfg_array.append("no network %s/%s" % (BGP_NETWORK, BGP_PL))

        SwitchVtyshUtils.vtysh_cfg_cmd(self.switch, cfg_array)


class Test_bgpd_network_cfg:
    def setup(self):
        pass

    def teardown(self):
        pass

    def setup_class(cls):
        Test_bgpd_network_cfg.test_var = bgpTest()

    def teardown_class(cls):
        Test_bgpd_network_cfg.test_var.net.stop()

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def __del__(self):
        del self.test_var

    def test_bgp_full(self):
        self.test_var.verify_bgp_running()
        self.test_var.configure_bgp()
        self.test_var.verify_bgp_router_id()
        self.test_var.verify_bgp_route()
        self.test_var.unconfigure_bgp()
        self.test_var.verify_no_bgp_route()
