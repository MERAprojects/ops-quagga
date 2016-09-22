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
# This case tests the show running-config command by comparing BGP config
# with the output of show running-config command.
#
# The following commands are tested:
#   * show running-config
#
# S1 [interface 1]
#

BGP1_ASN = "12"
BGP1_ROUTER_ID = "9.0.0.1"
BGP1_NETWORK = "11.0.0.0"

BGP2_ASN = "2"
BGP2_ROUTER_ID = "9.0.0.2"
BGP2_NETWORK = "12.0.0.0"

BGP1_NEIGHBOR = BGP2_ROUTER_ID
BGP1_NEIGHBOR_ASN = BGP2_ASN

BGP_NETWORK_PL = "8"
BGP_NETWORK_MASK = "255.0.0.0"
PATHS = "20"
DESCRIPTION = "abcd"
PASSWORD = "abcdef"
KEEPALIVE = "3"
HOLD = "10"
ALLOW_AS_IN_NUMBER = "7"
PEER_GROUP_NAME = "openswitch"

BGP1_CONFIG = ["router bgp %s" % BGP1_ASN,
               "bgp router-id %s" % BGP1_ROUTER_ID,
               "network %s/%s" % (BGP1_NETWORK, BGP_NETWORK_PL),
               "maximum-paths %s" % PATHS,
               "timers bgp %s %s" % (KEEPALIVE, HOLD),
               "neighbor %s remote-as %s" % (BGP1_NEIGHBOR, BGP1_NEIGHBOR_ASN),
               "neighbor %s description %s" % (BGP1_NEIGHBOR, DESCRIPTION),
               "neighbor %s password %s" % (BGP1_NEIGHBOR, PASSWORD),
               "neighbor %s timers %s %s" % (BGP1_NEIGHBOR, KEEPALIVE, HOLD),
               "neighbor %s allowas-in %s" % (BGP1_NEIGHBOR,
                                              ALLOW_AS_IN_NUMBER),
               "neighbor %s remove-private-AS" % BGP1_NEIGHBOR,
               "neighbor %s peer-group" % PEER_GROUP_NAME,
               "neighbor %s peer-group %s" % (BGP1_NEIGHBOR, PEER_GROUP_NAME),
               "neighbor %s soft-reconfiguration inbound" % BGP1_NEIGHBOR]

BGP_TEST_CONFIG = ["router bgp 3456",
                   "bgp router-id 1.1.1.1"]

NUM_OF_SWITCHES = 1
NUM_HOSTS_PER_SWITCH = 0

SWITCH_PREFIX = "s"


class myTopo(Topo):
    def build(self, hsts=0, sws=1, **_opts):
        self.hsts = hsts
        self.sws = sws

        switch = self.addSwitch("%s1" % SWITCH_PREFIX)


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
        info("\n########## Verifying bgp processes.. ##########\n")

        for switch in self.net.switches:
            pid = switch.cmd("pgrep -f bgpd").strip()
            assert (pid != ""), "bgpd process not running on switch %s" % \
                                switch.name

            info("### bgpd process exists on switch %s ###\n" % switch.name)

    def configure_bgp(self):
        info("\n########## Applying BGP configurations... ##########\n")
        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, BGP1_CONFIG)

    def verify_configs(self):
        info("\n########## Verifying all configurations.. ##########\n")

        bgp_cfg = BGP1_CONFIG
        switch = self.net.switches[0]

        for cfg in bgp_cfg:
            res = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg])
            assert res, "Config \"%s\" was not correctly configured!" % cfg

            info("### \"%s\" successfully configured ###\n" % cfg)


class Test_bgpd_show_running_config:
    def setup(self):
        pass

    def teardown(self):
        pass

    def setup_class(cls):
        Test_bgpd_show_running_config.test_var = bgpTest()

    def teardown_class(cls):
        Test_bgpd_show_running_config.test_var.net.stop()

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def __del__(self):
        del self.test_var

    def test_bgp_full(self):
        self.test_var.verify_bgp_running()
        self.test_var.configure_bgp()
        self.test_var.verify_configs()
