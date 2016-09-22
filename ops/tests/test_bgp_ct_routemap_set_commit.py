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

import pytest
from opsvsiutils.vtyshutils import *
from opsvsiutils.bgpconfig import *

#
# This test checks the following commands:
#   * ip prefix-list <prefix-list-name> seq <seq-num> (permit|deny) <prefix>
#   * route map <route-map-name> permit seq_num
#   *   description <description>
#   *   match ip address prefix-list <prefix-list>
#   *   set as-path prepend >asn>
#   *   set origin (egp|igp|incomplete)
#   *   set ipv6 next-hop global X:X::X:X
#   * neighbor <neighbor-router-id> route-map <prefix-list> (in|out)
#
# Topology:
#   S1 [interface 1]<--->[interface 2] S2
#
# Configuration of BGP1:
# ----------------------------------------------------------------------------
# !
# router bgp 1
#  bgp router-id 8.0.0.1
#  network 9.0.0.0/8
#  neighbor 8.0.0.2 remote-as 2
#  neighbor 8.0.0.2 route-map BGP1_IN in
# !
# ip prefix-list BGP1_IN seq 5 deny 11.0.0.0/8
# ip prefix-list BGP1_IN seq 10 permit 10.0.0.0/8
# !
# route-map BGP1_IN permit 5
#  description A route-map description for testing.
#  match ip address prefix-list BGP1_IN
#  set origin egp
#  set extcommunity rt 2:0 4:0
#  set extcommunity soo 3:0 5:0
#  set ipv6 next-hop 2001:db8::0:1
#  set as-path prepend 1
# !
#
# Configuration of BGP2:
# ----------------------------------------------------------------------------
# !
# router bgp 2
#  bgp router-id 8.0.0.2
#  network 10.0.0.0/8
#  network 11.0.0.0/8
#  neighbor 8.0.0.1 remote-as 1
# !
#
# Expected routes of BGP1:
# ----------------------------------------------------------------------------
# BGP table version is 0, local router ID is 8.0.0.1
#    Network          Next Hop            Metric LocPrf Weight Path
# *> 9.0.0.0          0.0.0.0                  0         32768 i
# *> 10.0.0.0         8.0.0.2                  0             0 2 i
#
# Expected routes of BGP2:
# ----------------------------------------------------------------------------
# BGP table version is 0, local router ID is 8.0.0.2
# Origin codes: i - IGP, e - EGP, ? - incomplete
#
#    Network          Next Hop            Metric LocPrf Weight Path
# *> 9.0.0.0          8.0.0.1                  0             0 1 i
# *> 10.0.0.0         0.0.0.0                  0         32768 i
# *> 11.0.0.0         0.0.0.0                  0         32768 i

NUM_OF_SWITCHES = 2
NUM_HOSTS_PER_SWITCH = 0
SWITCH_PREFIX = "s"

DEFAULT_PL = "8"
DEFAULT_NETMASK = "255.0.0.0"
RM_DESCRIPTION = "A route-map description for testing."


class myTopo(Topo):
    def build(self, hsts=0, sws=2, **_opts):
        self.hsts = hsts
        self.sws = sws

        switch = self.addSwitch("%s1" % SWITCH_PREFIX)
        switch = self.addSwitch(name="%s2" % SWITCH_PREFIX,
                                cls=PEER_SWITCH_TYPE,
                                **self.sopts)

        # Link the switches
        for i in range(1, NUM_OF_SWITCHES):
            self.addLink("%s%s" % (SWITCH_PREFIX, i),
                         "%s%s" % (SWITCH_PREFIX, i+1))


class bgpTest(OpsVsiTest):
    extcommunity_rt_str = "2:0"
    extcommunity_soo_str = "3:0"
    extcommunity_rt_str2 = "4:0"
    extcommunity_soo_str2 = "5:0"
    ipv6_nexthop_global_addr = ipv6_nexthop_local_addr = "2001:db8::0:1"

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

    def mininet_cli(self):
        CLI(self.net)

    def configure_switch_ips(self):
        info("\n########## Configuring switch IPs.. ##########\n")

        i = 0
        for switch in self.net.switches:
            bgp_cfg = self.bgpConfigArr[i]

            info("### Setting IP %s/%s on switch %s ###\n" %
                 (bgp_cfg.routerid, DEFAULT_PL, switch.name))

            # Configure the IPs between the switches
            if isinstance(switch, VsiOpenSwitch):
                switch.cmdCLI("configure terminal")
                switch.cmdCLI("interface 1")
                switch.cmdCLI("no shutdown")
                switch.cmdCLI("ip address %s/%s" % (bgp_cfg.routerid,
                                                    DEFAULT_PL))
                switch.cmdCLI("exit")
            else:
                switch.setIP(ip=bgp_cfg.routerid, intf="%s-eth1" % switch.name)

            i += 1

    def setup_bgp_config(self):
        info("\n########## Setup of BGP configurations... ##########\n")

        # Create BGP configurations
        self.bgpConfig1 = BgpConfig("1", "8.0.0.1", "9.0.0.0")
        self.bgpConfig2 = BgpConfig("2", "8.0.0.2", "10.0.0.0")

        # Add additional network for BGP2.
        self.bgpConfig2.addNetwork("11.0.0.0")

        # Add the neighbors for each BGP config
        self.bgpConfig1.addNeighbor(self.bgpConfig2)
        self.bgpConfig2.addNeighbor(self.bgpConfig1)

        self.bgpConfigArr = [self.bgpConfig1, self.bgpConfig2]

        # Configure "deny" for "in" of the second network of BGP2
        neighbor = self.bgpConfig1.neighbors[0]
        network = neighbor.networks[1]
        prefixList = PrefixList("BGP%s_IN" % self.bgpConfig1.asn, 5, "deny",
                                network, DEFAULT_PL)

        self.bgpConfig1.prefixLists.append(prefixList)
        self.bgpConfig1.addRouteMap(neighbor, prefixList, "in", "permit")

        # Configure so that the other route can be permitted
        network = neighbor.networks[0]
        prefixList = PrefixList("BGP%s_IN" % self.bgpConfig1.asn, 10, "permit",
                                network, DEFAULT_PL)

        self.bgpConfig1.prefixLists.append(prefixList)

    def apply_bgp_config(self):
        info("\n########## Applying BGP configurations... ##########\n")
        self.all_cfg_array = []

        i = 0
        for bgp_cfg in self.bgpConfigArr:
            info("### Applying configurations for BGP: %s ###\n" %
                 bgp_cfg.routerid)
            cfg_array = []

            # Add any prefix-lists
            self.add_prefix_list_configs(bgp_cfg, cfg_array)

            # Add route-map configs
            self.add_route_map_configs(bgp_cfg, cfg_array)

            SwitchVtyshUtils.vtysh_cfg_cmd(self.net.switches[i], cfg_array)

            del cfg_array[:]

            # Initiate BGP configuration
            cfg_array.append("router bgp %s" % bgp_cfg.asn)
            cfg_array.append("bgp router-id %s" % bgp_cfg.routerid)

            # Add the networks this bgp will be advertising
            for network in bgp_cfg.networks:
                cfg_array.append("network %s/%s" % (network, DEFAULT_PL))

            # Add the neighbors of this switch
            for neighbor in bgp_cfg.neighbors:
                cfg_array.append("neighbor %s remote-as %s" %
                                 (neighbor.routerid, neighbor.asn))

            # Add the neighbor route-maps configs
            self.add_neighbor_route_map_configs(bgp_cfg, cfg_array)

            SwitchVtyshUtils.vtysh_cfg_cmd(self.net.switches[i], cfg_array)

            # Add the configuration arrays to an array so that it can be used
            # for verification later.
            self.all_cfg_array.append(cfg_array)

            i += 1

    def add_route_map_configs(self, bgp_cfg, cfg_array):
        for routeMap in bgp_cfg.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))

            cfg_array.append("description %s" % RM_DESCRIPTION)

            cfg_array.append("match ip address prefix-list %s" %
                             prefixList.name)

    def add_prefix_list_configs(self, bgp_cfg, cfg_array):
        # Add any prefix-lists
        for prefixList in bgp_cfg.prefixLists:
            cfg_array.append("ip prefix-list %s seq %d %s %s/%s" %
                             (prefixList.name, prefixList.seq_num,
                              prefixList.action, prefixList.network,
                              prefixList.prefixLen))

    def add_neighbor_route_map_configs(self, bgp_cfg, cfg_array):
        # Add the route-maps
        for routeMap in bgp_cfg.routeMaps:
            neighbor = routeMap[0]
            prefixList = routeMap[1]
            dir = routeMap[2]

            cfg_array.append("neighbor %s route-map %s %s" %
                             (neighbor.routerid, prefixList.name, dir))

    def verify_bgp_running(self):
        info("\n########## Verifying bgp processes.. ##########\n")

        for switch in self.net.switches:
            pid = switch.cmd("pgrep -f bgpd").strip()
            assert (pid != ""), "bgpd process not running on switch %s" % \
                                switch.name

            info("### bgpd process exists on switch %s ###\n" % switch.name)

    def verify_bgp_configs(self):
        info("\n########## Verifying all configurations.. ##########\n")

        i = 0
        for switch in self.net.switches:
            bgp_cfg_array = self.all_cfg_array[i]

            for cfg in bgp_cfg_array:
                res = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg])
                assert res, "Config \"%s\" was not correctly configured!" % cfg

            i += 1

        info("### All configurations were verified successfully ###\n")

    def verify_bgp_routes(self):
        info("\n########## Verifying routes... ##########\n")

        # For each bgp, verify that it is indeed advertising itself
        self.verify_advertised_routes()

        # For each switch, verify the number of routes received
        self.verify_routes_received()

    def verify_advertised_routes(self):
        info("### Verifying advertised routes... ###\n")

        i = 0
        for bgp_cfg in self.bgpConfigArr:
            switch = self.net.switches[i]

            next_hop = "0.0.0.0"

            for network in bgp_cfg.networks:
                found = SwitchVtyshUtils.wait_for_route(switch, network,
                                                        next_hop)

                assert found, "Could not find route (%s -> %s) on %s" % \
                              (network, next_hop, switch.name)

            i += 1

    def verify_routes_received(self):
        info("### Verifying routes received... ###\n")

        switch = self.net.switches[0]
        neighbor = self.bgpConfig1.neighbors[0]
        next_hop = neighbor.routerid

        # First network of BGP2 should be permitted
        network = neighbor.networks[0]

        info("### Verifying route for switch %s ###\n" % switch.name)
        info("### Network: %s, Next-hop: %s - Should exist... ###\n" %
             (network, next_hop))

        found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop)

        assert found, "Route %s -> %s exists on %s" % \
                      (network, next_hop, switch.name)

        # Second network of BGP2 should NOT be permitted
        network = neighbor.networks[1]
        verify_route_exists = False

        info("### Verifying routes for switch %s ###\n" % switch.name)
        info("### Network: %s, Next-hop: %s - Should NOT exist... ###\n" %
             (network, next_hop))

        found = SwitchVtyshUtils.wait_for_route(switch, network, next_hop,
                                                verify_route_exists)

        assert not found, "Route %s -> %s does not exist on %s" % \
                          (network, next_hop, switch.name)

    def verify_routemap_set_as_path_prepend(self):
        info("\n########## Verifying route-map set as-path prepend "
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "set as-path prepend %s"%(self.bgpConfig1.asn)
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert exists, "Route-map as-path prepend was not set successfully"

        info("### Route-map as-path prepend was set successfully ###\n")

    def verify_routemap_no_set_as_path_prepend(self):
        info("\n########## Verifying route-map no set as-path prepend "
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "no set as-path prepend %s"%(self.bgpConfig1.asn)
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert not exists, "Route-map as-path prepend was not unset successfully"

        info("### Route-map as-path prepend was unset successfully ###\n")

    def verify_routemap_set_extcommunity_rt(self):
        info("\n########## Verifying route-map set extcommunity rt "
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "set extcommunity rt %s %s"%(self.extcommunity_rt_str
                , self.extcommunity_rt_str2)
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert exists, "Route-map extcommunity rt was not set "
        "successfully"

        info("### Route-map extcommunity rt was set successfully ###\n")

    def verify_routemap_no_set_extcommunity_rt(self):
        info("\n########## Verifying route-map no set extcommunity rt "
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "no set extcommunity rt %s %s"%(self. extcommunity_rt_str
                , self.extcommunity_rt_str2)
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert not exists, "Route-map extcommunity rt was not unset "
        "successfully"

        info("### Route-map extcommunity rt was unset successfully ###\n")

    def verify_routemap_set_extcommunity_soo(self):
        info("\n########## Verifying route-map set extcommunity soo "
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "set extcommunity soo %s %s"%(self.extcommunity_soo_str
                , self.extcommunity_soo_str2)
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert exists, "Route-map extcommunity soo was not set "
        "successfully"

        info("### Route-map extcommunity soo was set successfully ###\n")

    def verify_routemap_no_set_extcommunity_soo(self):
        info("\n########## Verifying route-map no set extcommunity soo "
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "no set extcommunity soo %s %s"%(self.extcommunity_soo_str
                , self.extcommunity_soo_str2)
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert not exists, "Route-map extcommunity soo was not unset "
        "successfully"

        info("### Route-map extcommunity soo was unset successfully ###\n")

    def verify_routemap_set_ipv6_next_hop_global(self):
        info("\n########## Verifying route-map set ipv6 next-hop global"
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "set ipv6 next-hop global %s"% \
                (self.ipv6_nexthop_global_addr)
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert exists, "Route-map ipv6 next-hop global ip was not set "
        "successfully"

        info("### Route-map ipv6 next-hop global ip was set successfully ###\n")

    def verify_routemap_no_set_ipv6_next_hop_global(self):
        info("\n########## Verifying route-map no set ipv6 next-hop global"
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "no set ipv6 next-hop global %s"% \
               (self.ipv6_nexthop_global_addr)
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert not exists, "Route-map ipv6 next-hop global ip was not unset "
        "successfully"

        info("### Route-map ipv6 next-hop global ip was unset successfully ###\n")

    def verify_routemap_set_origin(self, origin_type):
        info("\n########## Verifying route-map set origin"
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "set origin %s"%(str(origin_type))
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert exists, "Route-map origin %s was not set " \
        "successfully" % (str(origin_type))

        info("### Route-map origin %s was set successfully ###\n"%(str(origin_type)))

    def verify_routemap_no_set_origin(self, origin_type):
        info("\n########## Verifying route-map no set origin"
            "##########\n")
        cfg_array = []
        cfg_array.append("router bgp %s" % self.bgpConfig1.routerid)

        for routeMap in self.bgpConfig1.routeMaps:
            prefixList = routeMap[1]
            action = routeMap[3]

            cfg_array.append("route-map %s %s %d" %
                             (prefixList.name, action,
                              prefixList.seq_num))
            cfg_str = "no set origin %s"%(str(origin_type))
            cfg_array.append(cfg_str)

        switch = self.net.switches[0]
        SwitchVtyshUtils.vtysh_cfg_cmd(switch, cfg_array)

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg_str])
        assert not exists, "Route-map origin %s was not unset " \
        "successfully"%(str(origin_type))

        info("### Route-map origin %s was unset successfully ###\n"%(str(origin_type)))

    def verify_no_routemap(self):
        info("\n########## Verifying no route-map ##########\n")
        switch = self.net.switches[0]
        routeMap = self.bgpConfig1.routeMaps[0]
        prefixList = routeMap[1]
        action = routeMap[3]

        info("### Unconfiguring route-map ###\n")
        cfg = "route-map %s %s %d" % (prefixList.name, action,
                                      prefixList.seq_num)
        cmd = "no %s" % cfg

        SwitchVtyshUtils.vtysh_cfg_cmd(switch, [cmd])

        info("### Checking route-map config ###\n")

        exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg])
        assert not exists, "Config \"%s\" was not removed" % cfg

        info("### Route-map config was successfully removed ###\n")

    def verify_no_ip_prefix_list(self):
        info("\n########## Verifying no ip prefix-list ##########\n")
        switch = self.net.switches[0]
        for prefixList in self.bgpConfig1.prefixLists:
            cfg = "ip prefix-list %s seq %d %s %s/%s" % (prefixList.name,
                                                         prefixList.seq_num,
                                                         prefixList.action,
                                                         prefixList.network,
                                                         prefixList.prefixLen)
            cmd = "no %s" % cfg

            info("### Unconfiguring ip prefix-list %s ###\n" % prefixList.name)
            SwitchVtyshUtils.vtysh_cfg_cmd(switch, [cmd])

            info("### Checking ip prefix-list config ###\n")
            exists = SwitchVtyshUtils.verify_cfg_exist(switch, [cfg])
            assert not exists, "Config \"%s\" was not removed" % cfg

        info("### ip prefix-list configs were successfully removed ###\n")


class Test_bgpd_routemap:
    def setup(self):
        pass

    def teardown(self):
        pass

    def setup_class(cls):
        Test_bgpd_routemap.test_var = bgpTest()

    def teardown_class(cls):
        Test_bgpd_routemap.test_var.net.stop()

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def __del__(self):
        del self.test_var

    def test_bgp_full(self):
        self.test_var.setup_bgp_config()
        self.test_var.configure_switch_ips()
        self.test_var.verify_bgp_running()
        self.test_var.apply_bgp_config()
#        self.test_var.mininet_cli()
        self.test_var.verify_bgp_configs()
        self.test_var.verify_bgp_routes()
        self.test_var.verify_routemap_set_as_path_prepend()
        self.test_var.verify_routemap_no_set_as_path_prepend()
        self.test_var.verify_routemap_set_extcommunity_rt()
        self.test_var.verify_routemap_no_set_extcommunity_rt()
        self.test_var.verify_routemap_set_extcommunity_soo()
        self.test_var.verify_routemap_no_set_extcommunity_soo()
        self.test_var.verify_routemap_set_ipv6_next_hop_global()
        self.test_var.verify_routemap_no_set_ipv6_next_hop_global()
        self.test_var.verify_routemap_set_origin('egp')
        self.test_var.verify_routemap_no_set_origin('egp')
        self.test_var.verify_routemap_set_origin('igp')
        self.test_var.verify_routemap_no_set_origin('igp')
        self.test_var.verify_routemap_set_origin('incomplete')
        self.test_var.verify_routemap_no_set_origin('incomplete')
        self.test_var.verify_no_routemap()
        self.test_var.verify_no_ip_prefix_list()
