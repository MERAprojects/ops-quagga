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
# The following commands are tested:
#   * router bgp <asn>
#   * timers bgp <keepalive> <holdtime>
#   * no timers bgp
#
# S1 [interface 1]
#
BGP_ASN = "1"
TIMERS_BGP_KEEPALIVE = 5
TIMERS_BGP_HOLDTIME = 10

BGP_CONFIG = ["router bgp %s" % BGP_ASN,
              "timers bgp %d %d" % (TIMERS_BGP_KEEPALIVE, TIMERS_BGP_HOLDTIME)]

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

        switch = self.net.switches[0]

        pid = switch.cmd("pgrep -f bgpd").strip()
        assert (pid != ""), "bgpd process not running on switch"

        info("### bgpd process exists on switch ###\n")

    def configure_bgp(self):
        info("\n########## Applying BGP configurations... ##########\n")

        switch = self.net.switches[0]

        info("### Applying BGP config ###\n")
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, BGP_CONFIG)

    def verify_configs(self):
        info("\n########## Verifying all configurations.. ##########\n")

        bgp_cfg = BGP_CONFIG
        switch = self.net.switches[0]

        for cfg in bgp_cfg:
            res = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg])
            assert res, "Config \"%s\" was not correctly configured!" % cfg

        info("### All configurations were verified ###\n")

    def verify_no_timers(self):
        info("\n########## Verifying no timers bgp ##########\n")

        switch = self.net.switches[0]

        info("### Unconfiguring timers ###\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % BGP_ASN)
        cfg_array.append("no timers bgp")
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        info("### Verifying timers unconfigured ###\n")
        exists = SwitchVtyshUtils.verify_cfg_exist(switch, ["timers bgp"])

        assert not exists, "Timers were not unconfigured"

        info("### Timers unconfigured successfully ###\n")


class Test_bgpd_timers:
    def setup(self):
        pass

    def teardown(self):
        pass

    def setup_class(cls):
        Test_bgpd_timers.test_var = bgpTest()

    def teardown_class(cls):
        Test_bgpd_timers.test_var.net.stop()

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
        self.test_var.verify_no_timers()
