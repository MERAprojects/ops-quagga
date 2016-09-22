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
#
# This test configures a bgp neighbor in a bgp router
# and verifies its existence and its configuration as
# it gets updated from the daemon side.
# The CLI creates the basic object but the daemon sets
# some state & statistics values.  The test verifies that this
# happens properly.
#
# We need only one switch for this test.
#

BGP_ROUTER_ASN = "1"
BGP_NEIGHBOR_IPADDR = "1.1.1.1"
BGP_NEIGHBOR_REMOTE_AS = "1111"

BGP_NEIGHBOR_CONFIG = ["router bgp %s" % BGP_ROUTER_ASN,
                       "neighbor %s remote-as %s" % (BGP_NEIGHBOR_IPADDR,
                                                     BGP_NEIGHBOR_REMOTE_AS)]

NO_BGP_NEIGHBOR_CONFIG = ["router bgp %s" % BGP_ROUTER_ASN,
                          "no neighbor %s" % BGP_NEIGHBOR_IPADDR]

SHOW_BGP_NEIGHBORS = "show bgp neighbors"


class myTopo(Topo):
    def build(self, hsts=0, sws=1, **_opts):
        self.hsts = hsts
        self.sws = sws
        self.switch = self.addSwitch("s1")


class showBgpNeighborTest(OpsVsiTest):
    def setupNet(self):
        self.net = Mininet(topo=myTopo(hsts=0, sws=1,
                                       hopts=self.getHostOpts(),
                                       sopts=self.getSwitchOpts()),
                           switch=SWITCH_TYPE,
                           host=OpsVsiHost,
                           link=OpsVsiLink,
                           controller=None,
                           build=True)

        self.switch = self.net.switches[0]

    def bgp_neighbor_exists(self, show_output):
        if ((BGP_NEIGHBOR_IPADDR in show_output and
             BGP_NEIGHBOR_REMOTE_AS in show_output and
             "tcp_port_number" in show_output and
             "bgp_peer_keepalive_in_count" in show_output)):
            return True
        return False

    def add_bgp_neighbor_to_switch(self):
        info("\n########## Setting up switch with very basic "
             "BGP configuration ##########\n")

        SwitchVtyshUtils.vtysh_cfg_cmd(self.switch, BGP_NEIGHBOR_CONFIG)

        info("### Switch configuration complete ###\n")

    def verify_bgp_neighbor_exists(self):
        info("\n########## Verifying that the configured bgp "
             "neighbor DOES exist ##########\n")

        show_output = SwitchVtyshUtils.vtysh_cmd(self.switch,
                                                 SHOW_BGP_NEIGHBORS)
        assert (self.bgp_neighbor_exists(show_output)), \
            "TEST FAILED: bgp neighbor does NOT exist but it should"

        info("### Verified neighbor does exist ###\n")

    def delete_bgp_neighbor_from_switch(self):
        info("### Deleting bgp neighbor from the switch ###\n")
        SwitchVtyshUtils.vtysh_cfg_cmd(self.switch, NO_BGP_NEIGHBOR_CONFIG)

    def verify_bgp_neighbor_deleted(self):
        info("\n########## Verifying that the previously configured bgp "
             "neighbor does NOT exist ##########\n")

        self.delete_bgp_neighbor_from_switch()

        show_output = SwitchVtyshUtils.vtysh_cmd(self.switch,
                                                 SHOW_BGP_NEIGHBORS)
        assert (not self.bgp_neighbor_exists(show_output)), \
            "TEST FAILED: bgp neighbor DOES exist but it should NOT"

        info("### Verified neighbor does not exist ###\n")


class Test_bgpd_show_bgp_neighbor:
    def setup(self):
        pass

    def teardown(self):
        pass

    def setup_class(cls):
        Test_bgpd_show_bgp_neighbor.test_var = showBgpNeighborTest()

    def teardown_class(cls):
        Test_bgpd_show_bgp_neighbor.test_var.net.stop()

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def __del__(self):
        del self.test_var

    def test_show_bgp_neighbor(self):
        self.test_var.add_bgp_neighbor_to_switch()
        self.test_var.verify_bgp_neighbor_exists()
        self.test_var.verify_bgp_neighbor_deleted()
