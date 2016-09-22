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


BGP1_ASN = "1"
BGP1_ROUTER_ID = "9.0.0.1"
BGP1_NETWORK = "11.0.0.0"

BGP2_ASN = "2"
BGP2_ROUTER_ID = "9.0.0.2"
BGP2_NETWORK = "12.0.0.0"

BGP3_ASN = "3"
BGP3_ROUTER_ID = "9.0.0.3"
BGP3_NETWORK = "12.0.0.0"

BGP4_ASN = "4"
BGP4_ROUTER_ID = "9.0.0.4"
BGP4_NETWORK = "12.0.0.0"

BGP5_ASN = "5"
BGP5_ROUTER_ID = "9.0.0.5"
BGP5_NETWORK = "12.0.0.0"

# S1 Neighbors
BGP1_NEIGHBOR1 = "10.10.10.2"
BGP1_NEIGHBOR1_ASN = BGP2_ASN
BGP1_INTF1_IP = "10.10.10.1"

BGP1_NEIGHBOR2 = "20.20.20.2"
BGP1_NEIGHBOR2_ASN = BGP3_ASN
BGP1_INTF2_IP = "20.20.20.1"

BGP1_NEIGHBOR3 = "30.30.30.2"
BGP1_NEIGHBOR3_ASN = BGP4_ASN
BGP1_INTF3_IP = "30.30.30.1"

# S2 Neighbors
BGP2_NEIGHBOR1 = "10.10.10.1"
BGP2_NEIGHBOR1_ASN = BGP1_ASN
BGP2_INTF1_IP = "10.10.10.2"

BGP2_NEIGHBOR2 = "40.40.40.2"
BGP2_NEIGHBOR2_ASN = BGP5_ASN
BGP2_INTF2_IP = "40.40.40.1"

# S3 Neighbors
BGP3_NEIGHBOR1 = "20.20.20.1"
BGP3_NEIGHBOR1_ASN = BGP1_ASN
BGP3_INTF1_IP = "20.20.20.2"

BGP3_NEIGHBOR2 = "50.50.50.2"
BGP3_NEIGHBOR2_ASN = BGP5_ASN
BGP3_INTF2_IP = "50.50.50.1"

# S4 neighbors
BGP4_NEIGHBOR1 = "30.30.30.1"
BGP4_NEIGHBOR1_ASN = BGP1_ASN
BGP4_INTF1_IP = "30.30.30.2"

BGP4_NEIGHBOR2 = "60.60.60.2"
BGP4_NEIGHBOR2_ASN = BGP5_ASN
BGP4_INTF2_IP = "60.60.60.1"

# S5 Neighbors
BGP5_NEIGHBOR1 = "40.40.40.1"
BGP5_NEIGHBOR1_ASN = BGP2_ASN
BGP5_INTF1_IP = "40.40.40.2"

BGP5_NEIGHBOR2 = "50.50.50.1"
BGP5_NEIGHBOR2_ASN = BGP3_ASN
BGP5_INTF2_IP = "50.50.50.2"

BGP5_NEIGHBOR3 = "60.60.60.1"
BGP5_NEIGHBOR3_ASN = BGP4_ASN
BGP5_INTF3_IP = "60.60.60.2"

BGP_INTF_IP_ARR = [[BGP1_INTF1_IP, BGP1_INTF2_IP, BGP1_INTF3_IP],
                   [BGP2_INTF1_IP, BGP2_INTF2_IP],
                   [BGP3_INTF1_IP, BGP3_INTF2_IP],
                   [BGP4_INTF1_IP, BGP4_INTF2_IP],
                   [BGP5_INTF1_IP, BGP5_INTF2_IP, BGP5_INTF3_IP]]

BGP_NETWORK_PL = "8"
BGP_NETWORK_MASK = "255.0.0.0"
BGP_ROUTER_IDS = [BGP1_ROUTER_ID, BGP2_ROUTER_ID, BGP3_ROUTER_ID,
                  BGP4_ROUTER_ID, BGP5_ROUTER_ID]

BGP_MAX_PATHS = 5

BGP1_CONFIG = ["router bgp %s" % BGP1_ASN,
               "bgp router-id %s" % BGP1_ROUTER_ID,
               "network %s/%s" % (BGP1_NETWORK, BGP_NETWORK_PL),
               "neighbor %s remote-as %s" % (BGP1_NEIGHBOR1,
                                             BGP1_NEIGHBOR1_ASN),
               "neighbor %s remote-as %s" % (BGP1_NEIGHBOR2,
                                             BGP1_NEIGHBOR2_ASN),
               "neighbor %s remote-as %s" % (BGP1_NEIGHBOR3,
                                             BGP1_NEIGHBOR3_ASN),
               "maximum-paths %d" % BGP_MAX_PATHS]

BGP2_CONFIG = ["router bgp %s" % BGP2_ASN,
               "bgp router-id %s" % BGP2_ROUTER_ID,
               "neighbor %s remote-as %s" % (BGP2_NEIGHBOR1,
                                             BGP2_NEIGHBOR1_ASN),
               "neighbor %s remote-as %s" % (BGP2_NEIGHBOR2,
                                             BGP2_NEIGHBOR2_ASN)]

BGP3_CONFIG = ["router bgp %s" % BGP3_ASN,
               "bgp router-id %s" % BGP3_ROUTER_ID,
               "neighbor %s remote-as %s" % (BGP3_NEIGHBOR1,
                                             BGP3_NEIGHBOR1_ASN),
               "neighbor %s remote-as %s" % (BGP3_NEIGHBOR2,
                                             BGP3_NEIGHBOR2_ASN)]

BGP4_CONFIG = ["router bgp %s" % BGP4_ASN,
               "bgp router-id %s" % BGP4_ROUTER_ID,
               "neighbor %s remote-as %s" % (BGP4_NEIGHBOR1,
                                             BGP4_NEIGHBOR1_ASN),
               "neighbor %s remote-as %s" % (BGP4_NEIGHBOR2,
                                             BGP4_NEIGHBOR2_ASN)]

BGP5_CONFIG = ["router bgp %s" % BGP5_ASN,
               "bgp router-id %s" % BGP5_ROUTER_ID,
               "network %s/%s" % (BGP5_NETWORK, BGP_NETWORK_PL),
               "neighbor %s remote-as %s" % (BGP5_NEIGHBOR1,
                                             BGP5_NEIGHBOR1_ASN),
               "neighbor %s remote-as %s" % (BGP5_NEIGHBOR2,
                                             BGP5_NEIGHBOR2_ASN),
               "neighbor %s remote-as %s" % (BGP5_NEIGHBOR3,
                                             BGP5_NEIGHBOR3_ASN)]

BGP_CONFIGS = [BGP1_CONFIG, BGP2_CONFIG, BGP3_CONFIG, BGP4_CONFIG, BGP5_CONFIG]

NUM_OF_SWITCHES = 5
NUM_HOSTS_PER_SWITCH = 0
SWITCH_PREFIX = "s"
MAX_RTE_VERI_ATTEMPTS = 300
CMD_ROUTE = "show rib"


class myTopo(Topo):
    def build(self, hsts=0, sws=5, **_opts):
        self.hsts = hsts
        self.sws = sws

        switch = self.addSwitch("%s1" % SWITCH_PREFIX)
        switch = self.addSwitch(name="%s2" % SWITCH_PREFIX,
                                cls=PEER_SWITCH_TYPE,
                                **self.sopts)
        switch = self.addSwitch(name="%s3" % SWITCH_PREFIX,
                                cls=PEER_SWITCH_TYPE,
                                **self.sopts)
        switch = self.addSwitch(name="%s4" % SWITCH_PREFIX,
                                cls=PEER_SWITCH_TYPE,
                                **self.sopts)
        switch = self.addSwitch(name="%s5" % SWITCH_PREFIX,
                                cls=PEER_SWITCH_TYPE,
                                **self.sopts)

        # Connect the switches
        for i in irange(2, sws-1):
            self.addLink("%s1" % SWITCH_PREFIX,
                         "%s%s" % (SWITCH_PREFIX, i))

        for i in irange(2, sws-1):
            self.addLink("%s5" % SWITCH_PREFIX,
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
            j = 1
            for ip_addr in BGP_INTF_IP_ARR[i]:
                info("### Setting IP Address: %s ###\n" % ip_addr)
                if isinstance(switch, VsiOpenSwitch):
                    switch.cmdCLI("configure terminal")
                    switch.cmdCLI("interface %d" % j)
                    switch.cmdCLI("no shutdown")
                    switch.cmdCLI("ip address %s/%s" % (ip_addr,
                                                        BGP_NETWORK_PL))
                    switch.cmdCLI("exit")
                else:
                    switch.setIP(ip=ip_addr,
                                 intf="%s-eth%d" % (switch.name, j))
                j += 1
            i += 1

    def verify_bgp_running(self):
        info("\n########## Verifying bgp processes.. ##########\n")

        for switch in self.net.switches:
            pid = switch.cmd("pgrep -f bgpd").strip()
            assert (pid != ""), "bgpd process not running on switch %s" % \
                                switch.name

            info("### bgpd process exists on switch %s ###\n" % switch.name)

    def configure_bgp(self):
        info("\n########## Configuring BGP on all switches.. ##########\n")

        i = 0
        for switch in self.net.switches:
            cfg_array = BGP_CONFIGS[i]
            i += 1

            SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

    def verify_bgp_routes(self):
        info("### Verifying routes exist... ###\n")

        self.verify_bgp_route(self.net.switches[0], BGP2_NETWORK,
                              BGP1_NEIGHBOR1)
        self.verify_bgp_route(self.net.switches[0], BGP3_NETWORK,
                              BGP1_NEIGHBOR2)
        self.verify_bgp_route(self.net.switches[0], BGP4_NETWORK,
                              BGP1_NEIGHBOR3)

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

    def verify_route_removed(self, switch, network, next_hop):
        route_should_exist = False
        info("### Checking route to neighbor %s ###\n" % next_hop)
        found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop,
                                                route_should_exist)
        assert not found, "Route %s -> %s exists on %s" \
                          % (network, next_hop, switch.name)
        info("### Route to neighbor removed ###\n")

    def verify_all_routes_removed(self):
        info("### Waiting for routes to be removed ###\n")
        switch = self.net.switches[0]
        network = BGP2_NETWORK
        next_hop = BGP1_NEIGHBOR1
        self.verify_route_removed(switch, network, next_hop)

        network = BGP3_NETWORK
        next_hop = BGP1_NEIGHBOR2
        self.verify_route_removed(switch, network, next_hop)

        network = BGP4_NETWORK
        next_hop = BGP1_NEIGHBOR3
        self.verify_route_removed(switch, network, next_hop)

    def reconfigure_neighbors(self):
        info("### Reset connection to all peers from s1 ###\n")
        switch = self.net.switches[0]

        cfg_array = []
        cfg_array.append("router bgp %s" % BGP1_ASN)
        cfg_array.append("no neighbor %s" % BGP1_NEIGHBOR1)
        cfg_array.append("no neighbor %s" % BGP1_NEIGHBOR2)
        cfg_array.append("no neighbor %s" % BGP1_NEIGHBOR3)

        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        self.verify_all_routes_removed()

        info("### Reconfiguring neighbors on BGP1 ###\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % BGP1_ASN)
        cfg_array.append("neighbor %s remote-as %s" % (BGP1_NEIGHBOR1,
                                                       BGP1_NEIGHBOR1_ASN))
        cfg_array.append("neighbor %s remote-as %s" % (BGP1_NEIGHBOR2,
                                                       BGP1_NEIGHBOR2_ASN))
        cfg_array.append("neighbor %s remote-as %s" % (BGP1_NEIGHBOR3,
                                                       BGP1_NEIGHBOR3_ASN))
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        self.verify_bgp_routes()

    def get_number_of_paths_for_bgp1(self):

        switch = self.net.switches[0]

        route_info = SwitchVtyshUtils.vtysh_cmd(switch, CMD_ROUTE)

        multipath_count = 0
        if BGP1_NEIGHBOR1 in route_info:
            multipath_count += 1

        if BGP1_NEIGHBOR2 in route_info:
            multipath_count += 1

        if BGP1_NEIGHBOR3 in route_info:
            multipath_count += 1

        return multipath_count

    def verify_num_ip_route_exist_in_bgp1(self, no_route):
        info("\n### Verifying %d route(s) in %s ###\n" % (no_route, CMD_ROUTE))
        for i in range(MAX_RTE_VERI_ATTEMPTS):
            multipath_count = self.get_number_of_paths_for_bgp1()
            info("\n### Route Verification attempts %d ###\n" % i)
            if multipath_count == no_route:
                break
            time.sleep(1)
        return (multipath_count == no_route)

    def configure_ecmp(self, ecmp_status):
        s1 = self.net.switches[0]
        cfg_array = []
        if ecmp_status:
            cfg_array.append("no ip ecmp disable")
            SwitchVtyshUtils.vtysh_cfg_cmd(s1, cfg_array)
            info("### Verifying ecmp is enabled ###\n")
            exists = SwitchVtyshUtils.verify_cfg_exist(s1, ["ip ecmp disable"])
            assert not exists, "Fail to enable ip ecmp\n"
            info("### Successfully enable ecmp ###\n")
        else:
            cfg_array.append("ip ecmp disable")
            SwitchVtyshUtils.vtysh_cfg_cmd(s1, cfg_array)
            info("### Verifying ecmp disabled ###\n")
            exists = SwitchVtyshUtils.verify_cfg_exist(s1, ["ip ecmp disable"])
            assert exists, "Fail to disable ip ecmp\n"
            info("### Successfully disable ip ecmp ###\n")

    def configure_maxpaths(self, max_path):
        s1 = self.net.switches[0]
        cfg_array = []
        cfg_array.append("router bgp %s" % BGP1_ASN)
        if(max_path):
            cfg_array.append("maximum-paths 5")
            SwitchVtyshUtils.vtysh_cfg_cmd(s1, cfg_array)
            info("### Verifying maximum-paths configured ###\n")
            exists = SwitchVtyshUtils.verify_cfg_exist(s1, ["maximum-paths 5"])
            assert exists, "Fail to set maximum-paths to 5\n"
            info("### Successfully set maximum-paths to 5 ###\n")
        else:
            cfg_array.append("no maximum-paths")
            SwitchVtyshUtils.vtysh_cfg_cmd(s1, cfg_array)
            info("### Verifying maximum-paths config removed ###\n")
            exists = SwitchVtyshUtils.verify_cfg_exist(s1, ["maximum-paths"])
            assert not exists, "Maximum-paths was not unconfigured"
            info("### Successfully set no maximum-paths ###\n")

    def verify_max_paths(self):
        info("\n########## Verifying maximum-paths ##########\n")
        self.verify_bgp_routes()
        info("### Setting maximum-paths to 5 ###\n")
        self.configure_maxpaths(True)
        info("### Verifying that there are 3 multipaths ###\n")
        ret = self.verify_num_ip_route_exist_in_bgp1(3)
        assert ret, "Not all paths were detected."
        info("### All paths were detected ###\n")

    def verify_no_max_paths(self):
        info("\n########## Verifying no maximum-paths ##########\n")
        info("### Setting no maximum-paths ###\n")
        self.configure_maxpaths(False)
        info("### Verifying that there is only 1 path ###\n")
        ret = self.verify_num_ip_route_exist_in_bgp1(1)
        assert ret, "More than one paths are present."
        info("### Only 1 path detected after unsetting max-paths ###\n")

    def verify_maxpaths_ecmp_disabled(self,
                                      change_maxpaths=False,
                                      maxpaths_enabled=False):
        # Disable ecmp_config
        # Configure maxpath if applied
        # Verify global route if it has only 1 route
        info("\n########## Verifying maxpaths - ecmp disabled ##########\n")
        self.configure_ecmp(False)
        if change_maxpaths:
            if maxpaths_enabled:
                self.configure_maxpaths(True)
            else:
                self.configure_maxpaths(False)

        info("\n### Verify if ip route show 1 paths ###\n")
        ret = self.verify_num_ip_route_exist_in_bgp1(1)
        assert ret, "More than one paths are present."
        info("### Only 1 path detected after ecmp disabled ###\n")

    def verify_maxpaths_ecmp_enabled(self,
                                     change_maxpaths=False,
                                     maxpaths_enabled=False):
        # Enable ecmp_config, configure maxpath if applies
        # If not, it expects maxpath set previously
        # Verify global route if it has 3 routes (>1 route) if maxpath is set
        # and 1 route if maxpath is unset

        info("\n########## Verifying maxpaths - ecmp enabled ##########\n")
        self.configure_ecmp(True)
        no_paths = 3
        if change_maxpaths:
            if maxpaths_enabled:
                self.configure_maxpaths(True)
            else:
                self.configure_maxpaths(False)
                no_paths = 1
        info("\n### Verify if ip route show %s paths ###\n" % no_paths)
        ret = self.verify_num_ip_route_exist_in_bgp1(no_paths)
        assert ret, "Not all paths were detected."
        info("\n### %s paths detected after ecmp enabled ###\n" % no_paths)

    def config_maxpath_only(self):
        # Ecmp is previously enabled (by default),
        # Configure only maxpath to 5 expecting > 1 paths advertised
        # Configure no maxpath, expecting 1 path advertised
        self.verify_max_paths()
        self.verify_no_max_paths()
        self.verify_max_paths()

    def config_ecmp_only(self):
        # Disable ecmp, expecting 1 path advertised
        # Enable ecmp, expecting > 1 paths advertised
        self.verify_maxpaths_ecmp_disabled()
        self.verify_maxpaths_ecmp_enabled()

    def config_both_ecmp_maxpath(self):
        # Test if changing both maxpath and ecmp causing any issue
        # Disable ecmp, set max paths = 5, expecting 1 path advertised
        # Enable ecmp, set no maxpath, expecting 1 path advertised
        self.verify_maxpaths_ecmp_disabled(True, True)
        self.verify_maxpaths_ecmp_enabled(True, False)


class Test_bgpd_maximum_paths:
    def setup(self):
        pass

    def teardown(self):
        pass

    def setup_class(cls):
        Test_bgpd_maximum_paths.test_var = bgpTest()

    def teardown_class(cls):
        Test_bgpd_maximum_paths.test_var.net.stop()

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def run_test(self):
        info("\n########## Changing maxpaths only ##########\n")
        self.test_var.config_maxpath_only()
        info("\n########## Changing ecmp only ##########\n")
        self.test_var.config_ecmp_only()
        info("\n########## Changing ecmp and maxpaths ##########\n")
        self.test_var.config_both_ecmp_maxpath()

    def loop_test(self, loop=1):
        #Running loop to test stability and catching intermitten issue if any
        for i in range(loop):
            info("\n########## Test Loop %d ##########\n" % i)
            self.run_test()

    def __del__(self):
        del self.test_var

    def test_bgp_full(self):

        self.test_var.configure_switch_ips()
        self.test_var.verify_bgp_running()
        self.test_var.configure_bgp()
        self.test_var.verify_configs()
        # Enter value > 1 in the loop_test to test stability
        self.loop_test(1)
