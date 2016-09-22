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
INTERFACE_ADDRESS =  "8.0.0.1"
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

    def verify_bgp_running(self):
        info("\n########## Verifying bgp process.. ##########\n")

        switch = self.net.switches[0]
        pid = switch.cmd("pgrep -f bgpd").strip()
        assert (pid != ""), "bgpd process not running on switch %s" % \
                            switch.name

        info("### bgpd process exists on switch %s ###\n" % switch.name)

    def configure_bgp_without_router_id(self):
        info("\n########## Applying BGP configurations without router-id"\
             "... ##########\n")

        switch = self.net.switches[0]

        cfg_array = []
        cfg_array.append("router bgp %s" % BGP_ASN)
        cfg_array.append("network %s/%s" % (BGP_NETWORK, BGP_PL))

        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)
        sleep(10)

    def configure_interface(self):
        info("\n########## Applying BGP configurations without router-id"\
             "... ##########\n")

        switch = self.net.switches[0]

        cfg_array = []
        cfg_array.append("interface 1")
        cfg_array.append("ip address %s/%s" % (INTERFACE_ADDRESS, BGP_PL))
        cfg_array.append("no shutdown")

        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)
        sleep(10)

    def verify_bgp_router_id_by_zebra(self):
        info("\n########## Verifying BGP Router-ID configured by zebra"\
             "...##########\n")

        switch = self.net.switches[0]
        results = SwitchVtyshUtils.vtysh_cmd(switch, "sh ip bgp")

        found = INTERFACE_ADDRESS in results
        assert found, "BGP Router-ID %s not found" % INTERFACE_ADDRESS

        info("### BGP Router-ID %s found ###\n" % INTERFACE_ADDRESS)

    def configure_bgp(self):
        info("\n########## Applying BGP configurations with router-id"\
             "... ##########\n")

        switch = self.net.switches[0]

        cfg_array = []
        cfg_array.append("router bgp %s" % BGP_ASN)
        cfg_array.append("bgp router-id %s" % BGP_ROUTER_ID)
        cfg_array.append("network %s/%s" % (BGP_NETWORK, BGP_PL))

        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

    def verify_bgp_router_id(self):
        info("\n########## Verifying BGP Router-ID... ##########\n")

        switch = self.net.switches[0]
        results = SwitchVtyshUtils.vtysh_cmd(switch, "sh ip bgp")

        found = BGP_ROUTER_ID in results
        assert found, "BGP Router-ID %s not found" % BGP_ROUTER_ID

        info("### BGP Router-ID %s found ###\n" % BGP_ROUTER_ID)

    def unconfigure_bgp(self):
        info("\n########## Applying BGP configurations... ##########\n")

        switch = self.net.switches[0]

        cfg_array = []
        cfg_array.append("router bgp %s" % BGP_ASN)
        cfg_array.append("no bgp router-id %s" % BGP_ROUTER_ID)

        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

    def verify_no_bgp_router_id(self):
        info("\n########## Verifying BGP Router-ID... ##########\n")

        switch = self.net.switches[0]
        results = SwitchVtyshUtils.vtysh_cmd(switch, "sh ip bgp")

        found = BGP_ROUTER_ID in results
        assert not found, "BGP Router-ID %s was found" % BGP_ROUTER_ID

        info("### BGP Router-ID %s not found ###\n" % BGP_ROUTER_ID)


class Test_bgpd_router_id:
    def setup(self):
        pass

    def teardown(self):
        pass

    def setup_class(cls):
        Test_bgpd_router_id.test_var = bgpTest()

    def teardown_class(cls):
        Test_bgpd_router_id.test_var.net.stop()

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def __del__(self):
        del self.test_var

    def test_bgp_full(self):
        self.test_var.verify_bgp_running()
        self.test_var.configure_bgp_without_router_id()
        self.test_var.configure_interface()
        self.test_var.verify_bgp_router_id_by_zebra()
        self.test_var.configure_bgp()
        self.test_var.verify_bgp_router_id()
        self.test_var.unconfigure_bgp()
        self.test_var.verify_no_bgp_router_id()
